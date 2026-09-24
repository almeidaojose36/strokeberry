"""An original, deterministic botanical illustration for the starter project."""
import math
import random
from PIL import Image, ImageDraw


def create_sample(path):
    random.seed(42)
    im = Image.new('RGB', (1000, 820), (250, 249, 246))
    d = ImageDraw.Draw(im)
    def branch(points, width=7):
        d.line(points, fill='#656748', width=width, joint='curve')
    branch([(440, 760), (466, 635), (520, 501), (536, 375), (625, 220), (660, 89)])
    branch([(483, 594), (368, 495), (268, 331), (194, 223)], 5)
    branch([(530, 423), (692, 381), (806, 263)], 5)
    branch([(543, 365), (411, 244), (352, 132)], 4)
    def leaf(x, y, length, angle, color):
        theta = math.radians(angle)
        ux, uy = math.cos(theta), math.sin(theta)
        vx, vy = -uy, ux
        points = []
        for side in (1, -1):
            ts = range(31) if side == 1 else range(30, -1, -1)
            for i in ts:
                t = i / 30
                w = math.sin(math.pi*t)**.9 * length*.23 * side
                points.append((x + ux*t*length + vx*w, y+uy*t*length + vy*w))
        d.polygon(points, fill=color)
        d.line([(x,y),(x+ux*length*.94,y+uy*length*.94)], fill='#bac09a', width=2)
        for t in (.25,.4,.55,.7):
            for side in (-1,1):
                w = math.sin(math.pi*t)*length*.18*side
                d.line([(x+ux*(t-.07)*length,y+uy*(t-.07)*length), (x+ux*t*length+vx*w,y+uy*t*length+vy*w)], fill='#8c9d71', width=1)
    for item in [(466,638,172,165,'#657953'),(464,642,155,20,'#839367'),(496,551,154,-155,'#536c48'),(367,494,143,155,'#7b8e60'),(307,397,149,-172,'#536e4d'),(270,337,145,-98,'#6f8456'),(215,254,128,-153,'#849568'),(531,459,183,-20,'#586f4c'),(674,386,153,18,'#8e9a6a'),(762,312,158,-87,'#5c7854'),(625,224,145,-165,'#4c6747'),(644,171,122,-51,'#819361'),(659,113,105,-104,'#5f7854'),(420,255,132,-154,'#86966a'),(376,181,118,-88,'#5c754e')]:
        leaf(*item)
    def lemon(cx,cy,rx,ry,angle):
        layer=Image.new('RGBA',(rx*2+50,ry*2+50))
        p=ImageDraw.Draw(layer)
        p.ellipse((25,25,25+rx*2,25+ry*2), fill='#e7bc48',outline='#bd9c3b',width=2)
        p.ellipse((rx+12,12,rx+35,38),fill='#d2ab3e')
        for i in range(380):
            x=random.uniform(-rx,rx); y=random.uniform(-ry,ry)
            if (x/rx)**2+(y/ry)**2<.94:
                col=random.choice(['#efcc60','#d4ad3f','#eac451'])
                p.ellipse((rx+25+x,ry+25+y,rx+27+x,ry+27+y),fill=col)
        layer=layer.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
        im.paste(layer,(cx-layer.width//2,cy-layer.height//2),layer)
    lemon(423,408,69,101,28)
    lemon(625,497,75,105,-20)
    lemon(560,263,51,75,28)
    d=ImageDraw.Draw(im)
    for x,y in [(741,337),(313,310),(616,177)]:
        for a in range(0,360,72):
            px=x+math.cos(math.radians(a))*13;py=y+math.sin(math.radians(a))*13
            d.ellipse((px-10,py-10,px+10,py+10),fill='#f2eee3',outline='#c6c7ae',width=1)
        d.ellipse((x-5,y-5,x+5,y+5),fill='#d6ae4a')
    im.save(path)
