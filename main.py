import cv2
import numpy as np
import json
import os
import matplotlib.pyplot as plt


from Mask.config import Config
import Mask.utils as utils
import Mask.model as modellib
import Mask.visualize as visualize

segmentation_img_path = "Data/Segmentation"
orig_img_path = "Data/Images"
dir_path = os.path.dirname(os.path.realpath(__file__))
MODEL_DIR = dir_path + "/models/"
COCO_MODEL_PATH = "models/mask_rcnn_coco.h5"
if not os.path.isfile(COCO_MODEL_PATH):
    print(COCO_MODEL_PATH)
    raise Exception("You have to download mask_rcnn_coco.h5 inside Mask folder \n\
    You can find it here: https://github.com/matterport/Mask_RCNN/releases/download/v2.0/mask_rcnn_coco.h5")

class MolesConfig(Config):
    ''' 
    MolesConfig:
        Contain the configuration for the dataset + those in Config
    '''
    NAME = "moles"
    GPU_COUNT = 1 # put 2 or more if you are 1 or more gpu
    IMAGES_PER_GPU = 1 # if you are a gpu you are choose how many image to process per gpu
    NUM_CLASSES = 1 + 2  # background + (malignant , benign)
    IMAGE_MIN_DIM = 128
    IMAGE_MAX_DIM = 128

    # hyperparameter
    LEARNING_RATE = 0.001
    STEPS_PER_EPOCH = 100
    VALIDATION_STEPS = 5

class Metadata:
    ''' 
    Metadata:
        Contain everything about an image
        - Mask
        - Image
        - Description
    '''
    def __init__(self, classname, img, mask):
        self.img = img
        self.type = classname  # malignant , benign
        self.mask = mask

class MoleDataset(utils.Dataset):
    ''' 
    MoleDataset:
        Used to process the data
    '''
    def load_shapes(self, dataset, height, width):
        ''' Add the 2 class of skin cancer and put the metadata inside the model'''
        self.add_class("moles", 1, "malign")
        self.add_class("moles", 2, "benign")

        for i, info in enumerate(dataset):
            height, width, channels = info.img.shape
            self.add_image(source="moles", image_id=i, path=None,
                           width=width, height=height,
                           img=info.img, shape=(info.type, channels, (height, width)),
                           mask=info.mask, extra=info)

    def load_image(self, image_id):
        return self.image_info[image_id]["img"]

    def image_reference(self, image_id):
        if self.image_info[image_id]["source"] == "moles":
            return self.image_info[image_id]["shape"]
        else:
            super(self.__class__).image_reference(self, image_id)

    def load_mask(self, image_id):
        ''' load the mask and return mask and the class of the image '''
        info = self.image_info[image_id]
        shapes = info["shape"]
        mask = info["mask"].astype(np.uint8)
        class_ids=np.array([self.class_names.index(shapes[0])])
        return mask, class_ids.astype(np.int32)
    

config = MolesConfig()
all_info = []

# path of Data that contain Descriptions and Images
#path_data = input("Insert the path of Data [ Link /home/../ISIC-Archive-Downloader/Data/ ] : ")
#if not os.path.exists(path_data):
#    raise Exception(path_data + " Does not exists")

warning = True

# Load all the images, mask and description of the Dataset
for orig, seg in zip(os.listdir(orig_img_path), os.listdir(segmentation_img_path)):
    img = cv2.imread(os.path.join(orig_img_path,orig))
    mask = cv2.imread(os.path.join(segmentation_img_path, seg))
    classname = orig.split('.')[0].split('_')[1]
    if img is None or mask is None:
        continue
    img = cv2.resize(img, (128, 128))
    mask = cv2.resize(mask, (128, 128))
    
    info = Metadata(classname, img, mask)
    all_info.append(info)


# split the data into train and test
percentual = (len(all_info)*30)//100
np.random.shuffle(all_info)
train_data = all_info[:-percentual]
val_data = all_info[percentual+1:]
del all_info

# processing the data
dataset_train = MoleDataset()
dataset_train.load_shapes(train_data, config.IMAGE_SHAPE[0], config.IMAGE_SHAPE[1])
dataset_train.prepare()
dataset_val = MoleDataset()
dataset_val.load_shapes(val_data, config.IMAGE_SHAPE[0], config.IMAGE_SHAPE[1])
dataset_val.prepare()
del train_data
del val_data

# Show some random images to verify that everything is ok
image_ids = np.random.choice(dataset_train.image_ids, 3)
for image_id in image_ids:
    image = dataset_train.load_image(image_id)
    mask, class_ids = dataset_train.load_mask(image_id)
    visualize.display_top_masks(image, mask, class_ids, dataset_train.class_names)

# Create the MaskRCNN model
model = modellib.MaskRCNN(mode="training", config=config, model_dir=MODEL_DIR)

# Use as start point the coco model
model.load_weights(COCO_MODEL_PATH, by_name=True,
                   exclude=["mrcnn_class_logits", "mrcnn_bbox_fc",
                            "mrcnn_bbox", "mrcnn_mask"])

# Train the model on the train dataset
# First only the header layers
model.train(dataset_train, dataset_val,
            learning_rate=config.LEARNING_RATE,
            epochs=30,
            layers='heads')
# After all the layers 
model.train(dataset_train, dataset_val,
            learning_rate=config.LEARNING_RATE/10,
            epochs=90,
            layers="all")

print("Trained finished!")
