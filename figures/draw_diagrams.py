"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)

def render(out):
    d=Drawing((0,0,14.7,4.8))
    for name,x,y,w,label in [('s',1.1,2.15,1.6,'request'),('l',3.8,3.2,1.8,'lookup'),('w',3.8,1.1,2.3,'walk / replay'),('m',6.7,2.15,1.6,'merge'),('o',10.2,2.15,2.4,'owner check'),('b',13.4,2.15,2,'foreign use')]:
        d.box(name,x,y,w,.75,label,size=8.5)
    d.ax.add_patch(Rectangle((12.46,1.835),1.88,.63,fill=False,edgecolor='black',linewidth=.55,zorder=3))
    for a,b in [('s','l'),('s','w'),('l','m'),('w','m'),('m','o'),('o','b')]:d.edge(a,b,'e','w')
    for x,y,label in [(2.3,3,r'$\rho_1$'),(2.3,1.3,r'$\rho_2$'),(5.3,3,r'$\rho_3$'),(5.5,.95,r'$\rho_4$'),(7.95,2.5,r'$\rho_5$'),(11.95,2.5,r'$\rho_6$')]:d.text(x,y,label)
    d.line([(8.3,.65),(8.3,3.65)],dashed=True)
    d.text(8.3,4.12,'uniform cut\n'+r'$\rho_5=0$',size=8.5)
    d.save(out,'tpeg-overview')
    d=Drawing((0,0,14.1,4.2))
    for name,x,y,label in [('s',.7,2,'$s$'),('a',2.7,3,'$a$'),('c',2.7,1,'$c$'),('b',4.8,2,'$b$')]:d.box(name,x,y,1,.7,label)
    d.ax.add_patch(Rectangle((4.36,1.71),.88,.58,fill=False,edgecolor='black',linewidth=.55,zorder=3))
    for a,b in [('s','a'),('s','c'),('a','b'),('c','b')]:d.edge(a,b,'e','w')
    for x,y,label in [(1.55,2.95,'$x$'),(1.5,1.1,'$1-x$'),(3.85,2.95,'$1-x$'),(3.85,1.1,'$x$')]:d.text(x,y,label)
    for x,label in [(6.4,'state'),(9.1,'maximal open signature'),(12.6,'reaches $b$?')]:d.text(x,3.05,label,size=8)
    d.line([(5.7,2.72),(13.7,2.72)])
    for row,(state,sig) in enumerate([('$x=0$',r'$\{s\to c,\ a\to b\}$'),('$x=1$',r'$\{s\to a,\ c\to b\}$')]):
        y=2.15-.9*row;d.text(6.4,y,state,size=8.5);d.text(9.1,y,sig,size=8.5);d.text(12.6,y,'no',size=8.5)
    for x in [0,1]:
        sig={('s','a'):x,('a','b'):1-x,('s','c'):1-x,('c','b'):x}
        if sig['s','a']*sig['a','b'] or sig['s','c']*sig['c','b']:raise ValueError('Alternating paths example changed')
    d.save(out,'signature-cover')

def main():
    import tempfile
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--check',action='store_true');a=p.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True);render(a.output_dir)
    if a.check:
        with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
            render(Path(one));render(Path(two))
            for name in ['tpeg-overview','signature-cover']:
                if (Path(one)/(name+'.pdf')).read_bytes()!=(Path(two)/(name+'.pdf')).read_bytes():raise ValueError('Fresh exports differ: '+name)
    print('Two translation-path vector diagrams and binary example checks passed.')

if __name__=='__main__':main()
