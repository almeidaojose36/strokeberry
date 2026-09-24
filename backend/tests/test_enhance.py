import io

import cv2
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from backend.app import app
from backend.enhance import clean_background


def photographed_drawing():
    rng=np.random.default_rng(14)
    light=np.linspace(175,235,300)[None,:]+rng.normal(0,3,(240,300))
    image=np.repeat(np.uint8(np.clip(light,0,255))[:,:,None],3,axis=2)
    cv2.putText(image,'1',(20,55),cv2.FONT_HERSHEY_SIMPLEX,1.2,(25,25,25),3)
    cv2.rectangle(image,(110,70),(220,180),(30,145,220),-1)
    cv2.rectangle(image,(110,70),(220,180),(20,20,20),3)
    return image


def test_cleanup_flattens_paper_and_preserves_ink_and_color():
    original=photographed_drawing()
    result=np.array(clean_background(Image.fromarray(original),50))
    assert result.shape==original.shape
    assert np.all(result[200:]==[250,249,246])
    assert np.array_equal(result[90:160,130:200],original[90:160,130:200])
    assert np.max(result[np.max(original,axis=2)<40])<70
    before=np.count_nonzero(cv2.Canny(original[200:],10,20))
    after=np.count_nonzero(cv2.Canny(result[200:],10,20))
    assert before>100 and after==0


def test_cleanup_preview_endpoint_and_validation():
    client=TestClient(app)
    source=Image.fromarray(photographed_drawing());buffer=io.BytesIO();source.save(buffer,format='PNG')
    files={'file':('drawing.png',buffer.getvalue(),'image/png')}
    response=client.post('/api/images/clean-background',files=files,data={'strength':'50'})
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    assert Image.open(io.BytesIO(response.content)).size==source.size
    assert client.post('/api/images/clean-background',files=files,data={'strength':'101'}).status_code==422
    assert client.post('/api/images/clean-background',files={'file':('bad.png',b'bad','image/png')}).status_code==400
