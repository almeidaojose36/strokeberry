import io
import json
import shutil
import subprocess

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend import app as module
from backend import pipeline
from backend.steps import alignment, detect_panels, prepare_steps, StepFrames
from backend.steps import reading_regions, swept_scene, PAPER, color_layers, REVEAL_VERSION


def tutorial():
    image = Image.new('RGB', (420, 560), 'black')
    d = ImageDraw.Draw(image)
    for i, (x, y) in enumerate([(10, 40), (215, 40), (10, 285), (215, 285)]):
        d.rectangle((x,y,x+194,y+229),fill='white')
        d.line([(x+50,y+130),(x+100,y+70),(x+150,y+130)],fill='black',width=4)
        if i >= 1: d.rectangle((x+60,y+130,x+140,y+195),outline='black',width=4)
        if i >= 2: d.rectangle((x+95,y+155,x+115,y+195),fill='#555555')
        if i >= 3: d.rectangle((x+64,y+134,x+90,y+190),fill='#e67443')
    data = io.BytesIO();image.save(data,format='PNG');data.seek(0)
    return data


def config_for(folder):
    layout = detect_panels(folder)
    assert layout['detected'] and len(layout['crops']) == 4
    return module.StepConfig(stages=[{'crop': crop, 'label': f'Stage {i+1}', 'seconds': 2}
                                      for i,crop in enumerate(layout['crops'])]).model_dump()


def test_registration_recovers_translation():
    reference=np.full((200,180,3),250,np.uint8)
    cv2.line(reference,(40,40),(140,90),(20,20,20),3)
    cv2.line(reference,(140,90),(65,160),(20,20,20),3)
    moved=cv2.warpAffine(reference,np.float32([[1,0,16],[0,1,-12]]),(180,200),borderValue=(250,250,250))
    dx,dy,scale,confidence=alignment(moved,reference)
    assert dx == pytest.approx(-16,abs=4)
    assert dy == pytest.approx(12,abs=4)
    assert scale == pytest.approx(1,abs=.03)
    assert confidence > .7


def test_stages_are_continuous_and_finish_exactly(tmp_path):
    source=tmp_path/'source';source.mkdir();out=tmp_path/'out';out.mkdir()
    pipeline.prepare_image(tutorial(),source)
    config=config_for(source)
    scene=prepare_steps(source,out,config)
    assert scene['mode']=='steps' and scene['duration']==8
    assert pipeline.load_scene(out)['mode']=='steps'
    frames=StepFrames(out,scene)
    first,_,_,_=frames.frame(0)
    assert np.all(first == [250,249,246])
    for i,stage in enumerate(scene['stages']):
        finished,_,_,_=frames.frame(stage['start']+.96*(stage['end']-stage['start']))
        assert np.array_equal(finished,frames.targets[i])
        at_boundary,_,_,_=frames.frame(stage['end'])
        assert np.array_equal(finished,at_boundary)
    # The explicit final color panel survives processing.
    final=frames.targets[-1]
    assert np.count_nonzero(final[:,:,0].astype(int)-final[:,:,2] > 50) > 50


def test_steps_api_validation_and_original_preservation(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DATA',tmp_path);monkeypatch.setattr(module,'DB',tmp_path/'test.sqlite')
    module.init_db();client=TestClient(module.app)
    uploaded=client.post('/api/projects',files={'file':('tutorial.png',tutorial().getvalue(),'image/png')}).json()
    layout=client.get(f"/api/projects/{uploaded['id']}/step-layout").json()
    assert layout['detected']
    config=config_for(tmp_path/uploaded['id'])
    bad=json.loads(json.dumps(config));bad['stages'][0]['crop']['width']=1
    assert client.post(f"/api/projects/{uploaded['id']}/steps",json=bad).status_code==422
    response=client.post(f"/api/projects/{uploaded['id']}/steps",json=config)
    assert response.status_code==201
    result=response.json();assert result['id']!=uploaded['id']
    assert result['mode']=='steps' and len(result['stages'])==4
    assert client.get(result['stages'][0]['source']).status_code==200
    assert client.get(result['original']).content==client.get(uploaded['original']).content
    assert client.get(f"/media/{result['id']}/step-7.png").status_code==404


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
@pytest.mark.parametrize('whole_sheet', [False, True])
def test_steps_export_is_a_real_video(tmp_path,monkeypatch,whole_sheet):
    source=tmp_path/'source';source.mkdir();out=tmp_path/'out';out.mkdir()
    pipeline.prepare_image(tutorial(),source)
    config = config_for(source)
    if whole_sheet:
        config['stages'] = [dict(config['stages'][0], crop=dict(x=0,y=0,width=1,height=1), seconds=8)]
    prepare_steps(source,out,config)
    monkeypatch.setattr(pipeline,'dimensions',lambda _: (240,320))
    updates=[]
    path=pipeline.render(out,module.Settings(duration=8,pen=False).model_dump(),lambda p,s: updates.append(s))
    video=cv2.VideoCapture(str(path))
    assert video.isOpened() and int(video.get(cv2.CAP_PROP_FRAME_COUNT))==192
    ok,first=video.read();assert ok
    video.set(cv2.CAP_PROP_POS_FRAMES,191);ok,last=video.read();video.release();assert ok
    assert np.mean(np.abs(first.astype(float)-last.astype(float))) > 5
    assert any(('Step 1' if whole_sheet else 'Step 4') in stage for stage in updates)


def test_borderless_six_stage_grid(tmp_path):
    image=Image.new('RGB',(900,800),'white');draw=ImageDraw.Draw(image)
    for row in range(2):
        for col in range(3):
            x,y=col*300,row*400
            draw.line([(x+110,y+100),(x+160,y+60),(x+150,y+300)],fill='black',width=5)
            draw.line([(x+100,y+300),(x+200,y+300)],fill='black',width=5)
    raw=io.BytesIO();image.save(raw,format='PNG');raw.seek(0)
    pipeline.prepare_image(raw,tmp_path)
    result=detect_panels(tmp_path)
    assert result['detected'] and result['method']=='whitespace'
    assert result['rows']==2 and result['columns']==3
    assert len(result['crops'])==6
    for i,crop in enumerate(result['crops']):
        cx=(i%3*300+150)/900;cy=(i//3*400+200)/800
        assert crop['x']<cx<crop['x']+crop['width']
        assert crop['y']<cy<crop['y']+crop['height']
        assert crop['width']>.25 and crop['height']>.4


def test_single_drawing_does_not_claim_a_grid(tmp_path):
    image=Image.new('RGB',(400,400),'white');draw=ImageDraw.Draw(image)
    draw.ellipse((100,60,300,340),outline='black',width=6)
    raw=io.BytesIO();image.save(raw,format='PNG');raw.seek(0)
    pipeline.prepare_image(raw,tmp_path)
    assert not detect_panels(tmp_path)['detected']


def test_one_step_preserves_full_sheet_and_crop(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'DATA', tmp_path)
    monkeypatch.setattr(module, 'DB', tmp_path/'test.sqlite')
    module.init_db()
    client = TestClient(module.app)
    raw = tutorial().getvalue()
    uploaded = client.post('/api/projects', files={'file': ('sheet.png', raw, 'image/png')}).json()
    for crop in [dict(x=0,y=0,width=1,height=1), dict(x=.5,y=0,width=.5,height=.5)]:
        config = {'stages': [{'crop': crop, 'label': 'Whole image', 'seconds': 65,
                              'offset_x': 20, 'scale': .8}], 'align': True}
        response = client.post(f"/api/projects/{uploaded['id']}/steps", json=config)
        assert response.status_code == 201
        result = response.json()
        assert len(result['stages']) == 1 and result['duration'] == 65
        source = Image.open(io.BytesIO(raw)).convert('RGB')
        box = (round(crop['x']*source.width), round(crop['y']*source.height),
               round((crop['x']+crop['width'])*source.width), round((crop['y']+crop['height'])*source.height))
        expected = np.array(source.crop(box).resize((result['width'],result['height']),Image.Resampling.LANCZOS))
        frames = StepFrames(tmp_path/result['id'], result)
        assert np.array_equal(frames.frame(1)[0], expected)
        assert np.all(frames.frame(0)[0] == [250,249,246])
        assert client.get(uploaded['original']).content == raw
    assert client.post(f"/api/projects/{uploaded['id']}/steps", json={'stages': []}).status_code == 422


def test_reading_order_and_pen_only_reveal(tmp_path):
    target=np.full((100,100,3),255,np.uint8)
    target[:,49:51]=0;target[49:51,:]=0
    for x,y in [(10,10),(60,10),(10,60),(60,60)]:
        cv2.rectangle(target,(x,y),(x+25,y+25),(40,110,50),-1)
    regions=reading_regions(target)
    assert regions==[(0,0,50,50),(50,0,100,50),(0,50,50,100),(50,50,100,100)]
    previous=np.full_like(target,PAPER)
    timeline,_=swept_scene(previous,target,regions)
    Image.fromarray(target).save(tmp_path/'step-0.png')
    labels=color_layers(target,regions)
    Image.fromarray(labels).save(tmp_path/'rank-0.png')
    scene={'reveal_version':REVEAL_VERSION,'stages':[{'start':0,'end':1,'label':'Sheet','image':'step-0.png','rank':'rank-0.png','timeline':timeline}]}
    frames=StepFrames(tmp_path,scene)
    seen=[]
    for e in timeline:
        if e['kind']=='draw' and (not seen or seen[-1]!=e['clip']):seen.append(e['clip'])
    assert seen==[list(r) for r in regions]
    # No marks in later panels, even when their edges touch the current panel.
    for i,region in enumerate(regions[:-1]):
        end=max(e['end'] for e in timeline if e['clip']==list(region))
        frame=frames.frame(end*.9)[0]
        for x0,y0,x1,y1 in regions[i+1:]:
            assert np.array_equal(frame[y0:y1,x0:x1],previous[y0:y1,x0:x1])
    lift=next(e for e in timeline if e['kind']=='lift')
    assert np.array_equal(frames.frame((lift['start']+.2*(lift['end']-lift['start']))*.9)[0],
                          frames.frame((lift['start']+.8*(lift['end']-lift['start']))*.9)[0])
    assert np.array_equal(frames.frame(1)[0],target)
    # Browser and encoder expose exactly the same pixels, including backwards seeks.
    amounts=[0,.1,.4,.8,.2,1]
    script="""import {advanceSweep} from './frontend/src/sweep.js';
    let input='';for await(const chunk of process.stdin)input+=chunk;
    const {events,amounts,labels}=JSON.parse(input),state={};
    console.log(JSON.stringify(amounts.map(t=>Array.from(advanceSweep(state,100,100,0,t,events,labels)))));"""
    result=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps({'events':timeline,'amounts':amounts,'labels':labels.ravel().tolist()}),text=True,capture_output=True,check=True)
    for amount,mask in zip(amounts,json.loads(result.stdout)):
        frames.frame(amount*.9)
        assert np.array_equal(frames.mask.ravel(),np.array(mask,dtype=bool))


def test_colors_finish_before_next_color_and_never_bleed(tmp_path):
    # Touching, textured blue/yellow regions exercise brush overlap at the seam.
    target=np.full((48,64,3),255,np.uint8)
    target[4:44,4:32]=[40,150,240]
    target[4:44,32:60]=[250,210,20]
    target[10:20,8:20]=[110,190,250]
    target[26:32,40:50]=[255,235,80]
    labels=color_layers(target)
    assert set(np.unique(labels))=={0,1,2}
    paper=np.full_like(target,PAPER)
    timeline,_=swept_scene(paper,target,[(0,0,64,48)],labels)
    Image.fromarray(target).save(tmp_path/'step-0.png')
    Image.fromarray(labels).save(tmp_path/'rank-0.png')
    scene={'reveal_version':REVEAL_VERSION,'stages':[{'start':0,'end':1,'label':'Color','image':'step-0.png','rank':'rank-0.png','timeline':timeline}]}
    frames=StepFrames(tmp_path,scene)
    blue=[e for e in timeline if e['kind']=='draw' and e['color']==1]
    yellow=[e for e in timeline if e['kind']=='draw' and e['color']==2]
    assert max(e['end'] for e in blue)<=min(e['start'] for e in yellow)
    at_blue_end=frames.frame(max(e['end'] for e in blue)*.9)[0]
    assert np.array_equal(at_blue_end[labels==1],target[labels==1])
    assert np.array_equal(at_blue_end[labels==2],paper[labels==2])
    for e in blue:
        frame=frames.frame((e['start']+e['end'])/2*.9)[0]
        assert np.array_equal(frame[labels==2],paper[labels==2])
    assert np.array_equal(frames.frame(1)[0],target)


def test_text_and_complete_outlines_precede_mass_fill(tmp_path):
    target=np.full((140,180,3),255,np.uint8)
    cv2.putText(target,'A 4',(8,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(20,20,20),2,cv2.LINE_AA)
    cv2.rectangle(target,(15,50),(160,125),(30,150,240),-1)
    cv2.rectangle(target,(15,50),(160,125),(20,20,20),2,cv2.LINE_AA)
    labels=color_layers(target)
    # Gray antialiasing next to text must not wait for the shading pass.
    text_gray=(target[:40,:,0]>65)&(target[:40,:,0]<200)
    assert np.any(text_gray) and np.all(labels[:40][text_gray]==9)
    assert labels[85,80]==1
    paper=np.full_like(target,PAPER)
    timeline,_=swept_scene(paper,target,[(0,0,180,140)],labels)
    structure=[e for e in timeline if e['kind']=='draw' and e['color']==9]
    fill=[e for e in timeline if e['kind']=='draw' and e['color']!=9]
    assert structure and fill
    end=max(e['end'] for e in structure)
    assert end<=min(e['start'] for e in fill)
    Image.fromarray(target).save(tmp_path/'step-0.png')
    Image.fromarray(labels).save(tmp_path/'rank-0.png')
    scene={'reveal_version':REVEAL_VERSION,'stages':[{'start':0,'end':1,'label':'Drawing','image':'step-0.png','rank':'rank-0.png','timeline':timeline}]}
    frames=StepFrames(tmp_path,scene)
    frame=frames.frame(end*.9)[0]
    assert np.array_equal(frame[labels==9],target[labels==9])
    assert np.array_equal(frame[labels!=9],paper[labels!=9])
    assert np.array_equal(frames.frame(1)[0],target)


def test_character_finishes_before_clouds_and_colors(tmp_path):
    target=np.full((200,200,3),255,np.uint8)
    cv2.putText(target,'1',(10,23),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),2)
    # A cloud is higher on the page than the larger central character.
    cv2.ellipse(target,(145,32),(24,12),0,0,360,(20,20,20),2)
    cv2.ellipse(target,(100,117),(50,60),0,0,360,(60,160,240),-1)
    cv2.ellipse(target,(100,117),(50,60),0,0,360,(20,20,20),2)
    cv2.circle(target,(85,100),4,(20,20,20),-1)
    cv2.circle(target,(115,100),4,(20,20,20),-1)
    cv2.line(target,(20,165),(64,165),(20,20,20),2)
    regions=[(0,0,200,200)]
    labels=color_layers(target,regions)
    assert labels[20,145]==11  # cloud
    assert labels[117,50]==10  # character outline
    assert labels[117,100]==1  # blue interior
    assert np.any(labels[:25,:30]==9)
    paper=np.full_like(target,PAPER)
    timeline,_=swept_scene(paper,target,regions,labels)
    Image.fromarray(target).save(tmp_path/'step-0.png')
    Image.fromarray(labels).save(tmp_path/'rank-0.png')
    scene={'reveal_version':REVEAL_VERSION,'stages':[{'start':0,'end':1,'label':'Scene','image':'step-0.png','rank':'rank-0.png','timeline':timeline}]}
    frames=StepFrames(tmp_path,scene)
    for current,later in [(9,[10,11,1]),(10,[11,1]),(11,[1])]:
        end=max(e['end'] for e in timeline if e['kind']=='draw' and e['color']==current)
        frame=frames.frame(end*.9)[0]
        assert np.array_equal(frame[labels==current],target[labels==current])
        assert np.array_equal(frame[np.isin(labels,later)],paper[np.isin(labels,later)])
    assert np.array_equal(frames.frame(1)[0],target)
