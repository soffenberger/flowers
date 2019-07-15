import random
import glob
import subprocess
import os
from PIL import Image
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras import layers
from tensorflow.image import adjust_brightness, adjust_contrast, adjust_hue, adjust_saturation
from tensorflow.keras import backend as K
from tensorflow.keras.callbacks import Callback
import wandb
from wandb.keras import WandbCallback
from wandb.tensorflow import WandbHook
from datetime import datetime
import time
from tensorflow import Session
import random

run = wandb.init(project='superres')
config = run.config
#api = wandb.Api()
#ts = time.time()
#st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
#rn = api.run("soffenbe/superres/myrun_{0}".format(st))


config.num_epochs = 20
config.batch_size = 32
config.input_height = 32
config.input_width = 32
config.output_height = 256
config.output_width = 256

val_dir = 'data/test'
train_dir = 'data/train'

# automatically get the data if it doesn't exist
if not os.path.exists("data"):
    print("Downloading flower dataset...")
    subprocess.check_output(
        "mkdir data && curl https://storage.googleapis.com/wandb/flower-enhance.tar.gz | tar xzf - -C data", shell=True)

config.steps_per_epoch = len(
    glob.glob(train_dir + "/*-in.jpg")) // config.batch_size
config.val_steps_per_epoch = len(
    glob.glob(val_dir + "/*-in.jpg")) // config.batch_size

def preProcess(inputImageName, outputImageName):
    random.seed(datetime.now())
    sel = random.randint(1,30)
    inputImage = np.array(Image.open(inputImageName)) / 255.0
    outputImage = np.array(Image.open(outputImageName)) / 255.0
    #print(sel)
    #print(type(inputImage), type(outputImage))
    delta1 = random.uniform(0,0.5)
    delta2 = random.uniform(0,0.5)
    if (sel == 1): #random brightness and hue
        delta1 = random.uniform(0,0.5)
        #print(delta1, delta2)
        with Session() as sess:
            inputImage = adjust_brightness(inputImage, delta2)
            outputImage = adjust_brightness(outputImage, delta2)
            inputImage = sess.run(inputImage)
            outputImage = sess.run(outputImage)
    elif(sel == 2):
        #print(delta1, delta2)
        with Session() as sess:
            inputImage = adjust_contrast(inputImage, delta2)
            outputImage = adjust_contrast(outputImage, delta2)
            inputImage = sess.run(inputImage)
            outputImage = sess.run(outputImage)
    elif(sel == 3):
        with Session() as sess:
            inputImage = adjust_hue(inputImage, delta1)
            outputImage = adjust_hue(outputImage, delta1)
            inputImage = sess.run(inputImage)
            outputImage = sess.run(outputImage)
    elif(sel == 4):
        with Session() as sess:
            inputImage = adjust_saturation(inputImage, delta1)
            outputImage = adjust_saturation(outputImage, delta1)
            inputImage = sess.run(inputImage)
            outputImage = sess.run(outputImage)
    elif(sel == 5):
        inputImage = np.flipud(inputImage)
        outputImage = np.flipud(outputImage)
    elif(sel == 6):
        inputImage = np.fliplr(inputImage)
        outputImage = np.fliplr(outputImage)
    else:
        pass
    #print(type(inputImage), type(outputImage))
    return (inputImage, outputImage)

def image_generator(batch_size, img_dir):
    """A generator that returns small images and large images.  DO NOT ALTER the validation set"""
    input_filenames = glob.glob(img_dir + "/*-in.jpg")
    counter = 0
    random.shuffle(input_filenames)
    while True:
        small_images = np.zeros(
            (batch_size, config.input_width, config.input_height, 3))
        large_images = np.zeros(
            (batch_size, config.output_width, config.output_height, 3))
        if counter+batch_size >= len(input_filenames):
            counter = 0
        for i in range(batch_size):
            img = input_filenames[counter + i]
            (small_images[i], large_images[i]) = preProcess(img, img.replace("-in.jpg", "-out.jpg"))
        yield (small_images, large_images)
        counter += batch_size


def perceptual_distance(y_true, y_pred):
    """Calculate perceptual distance, DO NOT ALTER"""
    y_true *= 255
    y_pred *= 255
    rmean = (y_true[:, :, :, 0] + y_pred[:, :, :, 0]) / 2
    r = y_true[:, :, :, 0] - y_pred[:, :, :, 0]
    g = y_true[:, :, :, 1] - y_pred[:, :, :, 1]
    b = y_true[:, :, :, 2] - y_pred[:, :, :, 2]

    return K.mean(K.sqrt((((512+rmean)*r*r)/256) + 4*g*g + (((767-rmean)*b*b)/256)))


val_generator = image_generator(config.batch_size, val_dir)
in_sample_images, out_sample_images = next(val_generator)




class ImageLogger(Callback):
    def on_epoch_end(self, epoch, logs):
        preds = self.model.predict(in_sample_images)
        in_resized = []
        for arr in in_sample_images:
            # Simple upsampling
            in_resized.append(arr.repeat(8, axis=0).repeat(8, axis=1))
        wandb.log({
            "examples": [wandb.Image(np.concatenate([in_resized[i] * 255, o * 255, out_sample_images[i] * 255], axis=1)) for i, o in enumerate(preds)]
        }, commit=False)
        #saver = tf.train.Saver()
        #saver.save(sess, os.path.join(wandb.run.dir, "model.ckpt"))



model = Sequential()
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same',
                        input_shape=(config.input_width, config.input_height, 3)))
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same'))
model.add(layers.UpSampling2D())
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same'))
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same'))
model.add(layers.UpSampling2D())
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same'))
model.add(layers.Conv2D(3, (3, 3), activation='selu', padding='same'))
model.add(layers.UpSampling2D())

# DONT ALTER metrics=[perceptual_distance]
model.compile(optimizer='adam', loss='mse',
              metrics=[perceptual_distance])

model.fit_generator(image_generator(config.batch_size, train_dir),
                    steps_per_epoch=config.steps_per_epoch,
                    epochs=config.num_epochs, callbacks=[
                        ImageLogger(), WandbCallback()],
                    validation_steps=config.val_steps_per_epoch,
                    validation_data=val_generator)
print(dir(model))