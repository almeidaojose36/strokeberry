"""Paper cleanup for photographed drawings, preserving original dimensions."""
import cv2
import numpy as np
from PIL import Image


def clean_background(image, strength=50):
    rgb=np.array(image.convert('RGB'))
    h,w=rgb.shape[:2]
    scale=min(1.,1200/max(h,w))
    small=cv2.resize(rgb,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
    # Nearby bright paper estimates lighting without sharpening its grain.
    background=cv2.dilate(gray,np.ones((41,41),np.uint8))
    background=cv2.GaussianBlur(background,(0,0),12)
    background=cv2.resize(background,(w,h),interpolation=cv2.INTER_LINEAR).astype(np.float32)
    corrected=np.clip(rgb.astype(np.float32)*255/np.maximum(background[...,None],110),0,255)
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    pigment=np.uint8(hsv[:,:,1]>=60)
    pigment=cv2.morphologyEx(pigment,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    protected=cv2.dilate(pigment,np.ones((5,5),np.uint8))>0
    neutral=~protected
    threshold=12+strength*.55
    contrast=background-cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY).astype(np.float32)
    paper=neutral & (contrast<threshold) & (background>145)
    result=np.rint(corrected*np.array([250,249,246],np.float32)/255).astype(np.uint8)
    result[paper]=[250,249,246]
    foreground=np.uint8(neutral & ~paper & (background>145))
    count,components,stats,_=cv2.connectedComponentsWithStats(foreground,8)
    small=(stats[:,cv2.CC_STAT_AREA]<max(2,round(strength*.3)))
    small[0]=False
    # Remove isolated pale grain, keeping dark dots and fine punctuation.
    result[small[components] & (np.min(rgb,axis=2)>80)]=[250,249,246]
    # Colored pigments retain their original tones; cleanup targets neutral paper.
    result[~neutral]=rgb[~neutral]
    result[background<=145]=rgb[background<=145]
    return Image.fromarray(result)
