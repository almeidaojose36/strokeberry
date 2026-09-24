import io
import json
import shutil
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw
from backend import pipeline
from backend import app as module
from fastapi.testclient import TestClient


def illustration():
    image = Image.new('RGB', (240, 180), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 20, 140, 155), fill='#dab94f', outline='#274b35', width=3)
    draw.line([(150, 150), (180, 30), (210, 70)], fill='#274b35', width=4)
    data = io.BytesIO()
    image.save(data, format='PNG')
    data.seek(0)
    return data


def test_contours_and_reveal(tmp_path):
    scene = pipeline.prepare_image(illustration(), tmp_path)
    assert scene['strokes'] > 0
    assert scene['width'] == 240
    assert all(len(path) >= 2 for path in scene['paths'])
    reveal = np.array(Image.open(tmp_path / 'reveal.png'))
    assert len(np.unique(reveal)) > 10
    assert reveal.shape == (180, 240)


def test_flat_image_is_supported(tmp_path):
    raw = io.BytesIO()
    Image.new('RGB', (100, 100), 'white').save(raw, format='PNG')
    raw.seek(0)
    scene = pipeline.prepare_image(raw, tmp_path)
    assert scene['strokes'] == 0


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
@pytest.mark.parametrize("duration", [5, 65])
def test_encoded_video_reveals_source(tmp_path, monkeypatch, duration):
    pipeline.prepare_image(illustration(), tmp_path)
    monkeypatch.setattr(pipeline, 'dimensions', lambda _: (320, 180))
    updates = []
    output = pipeline.render(tmp_path, module.Settings(duration=duration, pen=False).model_dump(), lambda p,s: updates.append(p))
    video = cv2.VideoCapture(str(output))
    assert video.isOpened()
    assert int(video.get(cv2.CAP_PROP_FRAME_COUNT)) == duration * 24
    assert video.get(cv2.CAP_PROP_FPS) == 24
    ok, first = video.read()
    assert ok and np.mean(first) > 240
    video.set(cv2.CAP_PROP_POS_FRAMES, duration * 24 - 1)
    ok, last = video.read()
    video.release()
    assert ok
    assert np.mean(np.abs(first.astype(float)-last.astype(float))) > 10
    assert updates[-1] == 100
    assert not list(tmp_path.glob('*.partial.mp4'))


def test_api_upload_validation_and_file_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'DATA', tmp_path)
    monkeypatch.setattr(module, 'DB', tmp_path / 'test.sqlite')
    module.init_db()
    client = TestClient(module.app)
    bad = client.post('/api/projects', files={'file': ('bad.png', b'not an image', 'image/png')})
    assert bad.status_code == 400
    response = client.post('/api/projects', files={'file': ('drawing.png', illustration().getvalue(), 'image/png')})
    assert response.status_code == 201
    project = response.json()
    assert client.get(project['source']).status_code == 200
    assert client.get(f"/media/{project['id']}/scene.json").status_code == 404
    assert client.get('/media/studio.sqlite').status_code == 404
    assert client.get('/api/projects/unknown').status_code == 404
    assert client.post(f"/api/projects/{project['id']}/jobs", json={'duration': 1000}).status_code == 422
    assert client.get('/api/projects').json()[0]['id'] == project['id']
