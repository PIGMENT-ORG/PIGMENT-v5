#!/usr/bin/env python3
"""PIGMENT Language Compiler v3.0"""
import sys, re, os, base64, argparse
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum, auto

class TT(Enum):
    CANVAS=auto();PALETTE=auto();LAYER=auto();ZONE=auto()
    FEATURE=auto();SUBJECT=auto();SFUMATO=auto();CRAQUELURE=auto()
    ILLUMINATE=auto();SSS=auto();GLAZE=auto();IMPASTO=auto()
    FROM=auto();IN=auto();AT=auto();WITH=auto();CONTAINS=auto()
    TRUE=auto();FALSE=auto();ABSENT=auto()
    NUMBER=auto();NUM_UNIT=auto();COLOR_HEX=auto();STRING=auto()
    RESOLUTION=auto();IDENTIFIER=auto()
    LBRACE=auto();RBRACE=auto();COLON=auto();DOT=auto()
    COMMA=auto();PLUS=auto();MINUS=auto();EOF=auto()

KEYWORDS:Dict[str,TT]={
    'canvas':TT.CANVAS,'palette':TT.PALETTE,'layer':TT.LAYER,'zone':TT.ZONE,
    'feature':TT.FEATURE,'subject':TT.SUBJECT,'sfumato':TT.SFUMATO,
    'craquelure':TT.CRAQUELURE,'illuminate':TT.ILLUMINATE,'sss':TT.SSS,
    'glaze':TT.GLAZE,'impasto':TT.IMPASTO,'from':TT.FROM,'in':TT.IN,
    'at':TT.AT,'with':TT.WITH,'contains':TT.CONTAINS,
    'true':TT.TRUE,'false':TT.FALSE,'absent':TT.ABSENT,
}
IDENT_COMPAT={TT.FROM,TT.IN,TT.AT,TT.WITH,TT.CONTAINS,TT.CANVAS,TT.LAYER,TT.PALETTE,TT.ZONE,TT.GLAZE,TT.IMPASTO,TT.IDENTIFIER}

@dataclass
class Token:
    type:TT;value:Any;line:int;col:int
    def __repr__(self):return f"Token({self.type.name},{self.value!r},{self.line}:{self.col})"

class LexError(Exception):
    def __init__(self,m,l,c):super().__init__(f"[LexError line {l}:{c}] {m}")

class Lexer:
    def __init__(self,src):
        self.src=src.replace('\r\n','\n').replace('\r','\n');self.pos=0;self.line=1;self.col=1
    def err(self,m):raise LexError(m,self.line,self.col)
    @property
    def ch(self):return self.src[self.pos] if self.pos<len(self.src) else ''
    def look(self,n=1):p=self.pos+n;return self.src[p] if p<len(self.src) else ''
    def eat(self):
        if self.pos>=len(self.src):return ''
        c=self.src[self.pos];self.pos+=1
        if c=='\n':self.line+=1;self.col=1
        else:self.col+=1
        return c
    def skip_ws(self):
        while self.pos<len(self.src) and self.ch in ' \t\n\r':self.eat()
    def read_comment(self):
        while self.ch and self.ch!='\n':self.eat()
    def read_number(self,neg=False):
        ln,co=self.line,self.col;s=self.pos
        while self.ch.isdigit() or self.ch=='.':self.eat()
        raw=self.src[s:self.pos];val=float(raw) if '.' in raw else int(raw)
        if neg:val=-val
        if self.ch=='x' and self.look().isdigit():
            self.eat();s2=self.pos
            while self.ch.isdigit():self.eat()
            return Token(TT.RESOLUTION,(int(abs(val)),int(self.src[s2:self.pos])),ln,co)
        if self.ch.isalpha():
            us=self.pos
            while self.ch.isalpha():self.eat()
            return Token(TT.NUM_UNIT,(val,self.src[us:self.pos]),ln,co)
        return Token(TT.NUMBER,val,ln,co)
    def read_hex(self):
        ln,co=self.line,self.col;self.eat();s=self.pos
        while self.ch in '0123456789abcdefABCDEF':self.eat()
        h=self.src[s:self.pos].lower()
        if len(h)==3:h=h[0]*2+h[1]*2+h[2]*2
        if len(h)!=6:self.err(f"Bad hex: #{h}")
        return Token(TT.COLOR_HEX,h,ln,co)
    def read_string(self,q):
        ln,co=self.line,self.col;self.eat();buf=[]
        while self.ch and self.ch!=q:
            if self.ch=='\\':
                self.eat()
                buf.append({'n':'\n','t':'\t','\\':'\\','"':'"',"'":"'"}.get(self.ch,self.ch));self.eat()
            else:buf.append(self.eat())
        if not self.ch:self.err("Unterminated string")
        self.eat();return Token(TT.STRING,''.join(buf),ln,co)
    def read_ident(self):
        ln,co=self.line,self.col;s=self.pos
        while self.ch.isalnum() or self.ch=='_' or(self.ch=='-' and(self.look().isalnum() or self.look()=='_')):self.eat()
        word=self.src[s:self.pos];return Token(KEYWORDS.get(word,TT.IDENTIFIER),word,ln,co)
    def tokenize(self):
        toks=[]
        while True:
            self.skip_ws()
            if not self.ch:toks.append(Token(TT.EOF,None,self.line,self.col));break
            ln,co=self.line,self.col;c=self.ch
            if c=='-' and self.look()=='-':self.eat();self.read_comment();continue
            elif c=='{':self.eat();toks.append(Token(TT.LBRACE,'{',ln,co))
            elif c=='}':self.eat();toks.append(Token(TT.RBRACE,'}',ln,co))
            elif c==':':self.eat();toks.append(Token(TT.COLON,':',ln,co))
            elif c=='.':self.eat();toks.append(Token(TT.DOT,'.',ln,co))
            elif c==',':self.eat();toks.append(Token(TT.COMMA,',',ln,co))
            elif c=='+':
                self.eat()
                if self.ch.isdigit() or self.ch=='.':toks.append(self.read_number())
                else:toks.append(Token(TT.PLUS,'+',ln,co))
            elif c=='-':
                if self.look().isdigit() or self.look()=='.':
                    self.eat();toks.append(self.read_number(True))
                else:self.eat();toks.append(Token(TT.MINUS,'-',ln,co))
            elif c=='#':toks.append(self.read_hex())
            elif c in '"\'':toks.append(self.read_string(c))
            elif c.isdigit() or(c=='.' and self.look().isdigit()):toks.append(self.read_number())
            elif c.isalpha() or c=='_':toks.append(self.read_ident())
            else:self.err(f"Unexpected character {c!r}")
        return toks

@dataclass
class PaletteColor:
    modifier:Optional[str];hex_value:str
@dataclass
class CanvasNode:
    properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class PaletteNode:
    colors:Dict[str,Any]=field(default_factory=dict)
@dataclass
class PropertyNode:
    key:str;value:Any
@dataclass
class IlluminateNode:
    regions:Dict[str,Any]=field(default_factory=dict)
@dataclass
class SSSNode:
    properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class SfumatoNode:
    label:Optional[str];properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class CraquelureNode:
    properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class GlazeNode:
    properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class ImpastoNode:
    properties:Dict[str,Any]=field(default_factory=dict)
@dataclass
class ZoneNode:
    name:str;statements:List[Any]=field(default_factory=list)
@dataclass
class FeatureNode:
    name:str;properties:Dict[str,Any]=field(default_factory=dict);blocks:List[Any]=field(default_factory=list)
@dataclass
class LayerNode:
    name:str;properties:Dict[str,Any]=field(default_factory=dict);statements:List[Any]=field(default_factory=list)
@dataclass
class SubjectNode:
    name:str;statements:List[Any]=field(default_factory=list)
@dataclass
class PaintingNode:
    canvas:Optional[CanvasNode]=None;palette:Optional[PaletteNode]=None
    layers:List[LayerNode]=field(default_factory=list);subjects:List[SubjectNode]=field(default_factory=list)

class ParseError(Exception):
    def __init__(self,m,l,c):super().__init__(f"[ParseError line {l}:{c}] {m}")

class Parser:
    def __init__(self,tokens):self.toks=tokens;self.pos=0
    @property
    def cur(self):return self.toks[self.pos]
    def peek(self,n=1):p=self.pos+n;return self.toks[p] if p<len(self.toks) else self.toks[-1]
    def err(self,m):raise ParseError(m,self.cur.line,self.cur.col)
    def adv(self):
        t=self.toks[self.pos]
        if self.pos<len(self.toks)-1:self.pos+=1
        return t
    def expect(self,tt):
        if self.cur.type!=tt:self.err(f"Expected {tt.name}, got {self.cur.type.name} ({self.cur.value!r})")
        return self.adv()
    def check(self,*types):return self.cur.type in types
    def _nc(self):return self.peek().type==TT.COLON
    def _nb(self):return self.peek().type==TT.LBRACE
    def parse(self):
        p=PaintingNode()
        while not self.check(TT.EOF):
            if self.check(TT.CANVAS):p.canvas=self.parse_canvas()
            elif self.check(TT.PALETTE):p.palette=self.parse_palette()
            elif self.check(TT.LAYER):p.layers.append(self.parse_layer())
            elif self.check(TT.SUBJECT):p.subjects.append(self.parse_subject())
            else:self.err(f"Expected top-level block, got {self.cur.type.name}")
        return p
    def parse_canvas(self):
        self.expect(TT.CANVAS);n=CanvasNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();n.properties[k]=v
        self.expect(TT.RBRACE);return n
    def parse_palette(self):
        self.expect(TT.PALETTE);n=PaletteNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):nm=self.parse_ident();self.expect(TT.COLON);n.colors[nm]=self.parse_pal_color()
        self.expect(TT.RBRACE);return n
    def parse_layer(self):
        self.expect(TT.LAYER);nm=self.parse_ident();n=LayerNode(name=nm);self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):
            s=self.parse_stmt()
            if s:n.statements.append(s)
        self.expect(TT.RBRACE);return n
    def parse_subject(self):
        self.expect(TT.SUBJECT);nm=self.parse_ident();n=SubjectNode(name=nm);self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):
            s=self.parse_stmt()
            if s:n.statements.append(s)
        self.expect(TT.RBRACE);return n
    def parse_stmt(self):
        if self.check(TT.ZONE):return self.parse_zone()
        if self.check(TT.FEATURE):return self.parse_feature()
        if self.check(TT.SFUMATO) and not self._nc():return self.parse_sfumato()
        if self.check(TT.SSS) and not self._nc():return self.parse_sss()
        if self.check(TT.ILLUMINATE) and not self._nc():return self.parse_illuminate()
        if self.check(TT.CRAQUELURE) and not self._nc():return self.parse_craquelure()
        if self.check(TT.GLAZE) and not self._nc():return self.parse_glaze()
        if self.check(TT.IMPASTO) and not self._nc():return self.parse_impasto()
        if self.cur.type==TT.IDENTIFIER and self._nb():return self.parse_named_block()
        PT=IDENT_COMPAT|{TT.SFUMATO,TT.SSS,TT.ILLUMINATE,TT.CRAQUELURE,TT.GLAZE,TT.IMPASTO,TT.TRUE,TT.FALSE,TT.ABSENT}
        if self.cur.type in PT:k,v=self.parse_prop();return PropertyNode(key=k,value=v)
        self.err(f"Unexpected token {self.cur.type.name} ({self.cur.value!r})")
    def parse_named_block(self):
        nm=self.parse_ident();node=ZoneNode(name=nm);self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):
            s=self.parse_stmt()
            if s:node.statements.append(s)
        self.expect(TT.RBRACE);return node
    def parse_zone(self):
        self.expect(TT.ZONE);nm=self.parse_ident();node=ZoneNode(name=nm)
        if self.check(TT.LBRACE):
            self.adv()
            while not self.check(TT.RBRACE,TT.EOF):
                s=self.parse_stmt()
                if s:node.statements.append(s)
            self.expect(TT.RBRACE)
        return node
    def parse_feature(self):
        self.expect(TT.FEATURE);nm=self.parse_ident();node=FeatureNode(name=nm);self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):
            s=self.parse_stmt()
            if not s:continue
            if isinstance(s,PropertyNode):node.properties[s.key]=s.value
            else:node.blocks.append(s)
        self.expect(TT.RBRACE);return node
    def parse_sfumato(self):
        self.expect(TT.SFUMATO);label=None;props={}
        OK=IDENT_COMPAT|{TT.SFUMATO,TT.SSS,TT.CRAQUELURE,TT.GLAZE,TT.IMPASTO,TT.IDENTIFIER}
        if self.cur.type in OK and not self._nc() and not self._nb():label=self.parse_ident()
        if self.check(TT.LBRACE):
            self.adv()
            while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();props[k]=v
            self.expect(TT.RBRACE)
        return SfumatoNode(label=label,properties=props)
    def parse_sss(self):
        self.expect(TT.SSS);node=SSSNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();node.properties[k]=v
        self.expect(TT.RBRACE);return node
    def parse_illuminate(self):
        self.expect(TT.ILLUMINATE);node=IlluminateNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();node.regions[k]=v
        self.expect(TT.RBRACE);return node
    def parse_craquelure(self):
        self.expect(TT.CRAQUELURE);node=CraquelureNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();node.properties[k]=v
        self.expect(TT.RBRACE);return node
    def parse_glaze(self):
        self.expect(TT.GLAZE);node=GlazeNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();node.properties[k]=v
        self.expect(TT.RBRACE);return node
    def parse_impasto(self):
        self.expect(TT.IMPASTO);node=ImpastoNode();self.expect(TT.LBRACE)
        while not self.check(TT.RBRACE,TT.EOF):k,v=self.parse_prop();node.properties[k]=v
        self.expect(TT.RBRACE);return node
    def parse_prop(self):k=self.parse_ident();self.expect(TT.COLON);v=self.parse_value();return k,v
    def parse_value(self):
        t=self.cur;MODS={'warm','cool','light','dark','muted','deep','pale'}
        if t.type==TT.NUM_UNIT:self.adv();return t.value
        if t.type==TT.NUMBER:
            self.adv()
            if self.check(TT.COLON) and self.peek().type==TT.NUMBER:
                self.adv();t2=self.adv();return{'ratio':(int(t.value),int(t2.value))}
            return t.value
        if t.type==TT.COLOR_HEX:self.adv();return{'hex':t.value}
        if t.type==TT.STRING:self.adv();return t.value
        if t.type==TT.TRUE:self.adv();return True
        if t.type==TT.FALSE:self.adv();return False
        if t.type==TT.ABSENT:self.adv();return 'absent'
        if t.type==TT.RESOLUTION:self.adv();return{'resolution':t.value}
        if t.type==TT.IDENTIFIER and t.value in MODS and self.peek().type==TT.COLOR_HEX:
            mod=self.adv().value;h=self.adv().value;return PaletteColor(modifier=mod,hex_value=h)
        if t.type in IDENT_COMPAT or t.type==TT.IDENTIFIER:return self.parse_qref()
        self.err(f"Expected value, got {t.type.name} ({t.value!r})")
    def parse_pal_color(self):
        MODS={'warm','cool','light','dark','muted','deep','pale'};modifier=None
        if self.cur.type==TT.IDENTIFIER and self.cur.value in MODS:modifier=self.adv().value
        if self.check(TT.COLOR_HEX):return PaletteColor(modifier=modifier,hex_value=self.adv().value)
        if self.cur.type in IDENT_COMPAT:ref=self.parse_qref();return{'modifier':modifier,'ref':ref}
        self.err(f"Expected color, got {self.cur.type.name}")
    def parse_ident(self):
        OK=IDENT_COMPAT|{TT.SFUMATO,TT.SSS,TT.ILLUMINATE,TT.CRAQUELURE,TT.GLAZE,TT.IMPASTO,TT.IDENTIFIER,TT.TRUE,TT.FALSE,TT.ABSENT}
        if self.cur.type in OK:return self.adv().value
        self.err(f"Expected identifier, got {self.cur.type.name} ({self.cur.value!r})")
    def parse_qref(self):
        parts=[self.parse_ident()]
        while self.check(TT.DOT):self.adv();parts.append(self.parse_ident())
        return'.'.join(parts)

# ── Color utils ──────────────────────────────────────────────────

def h2rgb(h):return int(h[0:2],16)/255,int(h[2:4],16)/255,int(h[4:6],16)/255
def apply_mod(r,g,b,m):
    if m=='warm':return min(1,r+.06),min(1,g+.02),max(0,b-.06)
    if m=='cool':return max(0,r-.06),max(0,g-.02),min(1,b+.06)
    if m=='light':return min(1,r+.10),min(1,g+.10),min(1,b+.10)
    if m=='dark':return max(0,r-.10),max(0,g-.10),max(0,b-.10)
    if m=='muted':a=(r+g+b)/3;return r*.65+a*.35,g*.65+a*.35,b*.65+a*.35
    if m=='deep':return min(1,r*1.15),min(1,g*1.15),min(1,b*1.15)
    if m=='pale':return min(1,r*.4+.6),min(1,g*.4+.6),min(1,b*.4+.6)
    return r,g,b
def v3(r,g,b):return f"vec3({r:.5f},{g:.5f},{b:.5f})"

# ── Code Generator ───────────────────────────────────────────────
# Coordinate system: Y-UP (standard math/WebGL)
#   uv.y = +0.5 = TOP  (sky)
#   uv.y =  0.0 = middle
#   uv.y = -0.5 = BOTTOM
# Portrait 77:53 => aspect=53/77≈0.688, uv.x ∈ [−0.344,+0.344]
# Scene layout:
#   sky/clouds:    y > 0.15
#   mountains:     y ≈ 0.05–0.30 (appear above horizon, below sky)
#   figure face:   center (0, +0.10)   ← above canvas midpoint = upper half
#   figure hair:   center (0, +0.24)   ← above face
#   figure gown:   center (0, −0.22)   ← below face

GROUND_HEX={'poplar':'c8b89a','oak':'b8a888','linen':'f0e6d0','cotton':'ece0cc','paper':'f5f0e0','copper':'b87050','wall':'e8e0d0'}
LIGHT_DIRS={'upper-left':(-0.707,0.707),'upper-right':(0.707,0.707),'lower-left':(-0.5,-0.5),'lower-right':(0.5,-0.5),'top':(0,1),'bottom':(0,-1),'left':(-1,0),'right':(1,0),'front':(0.0,0.1),'golden-hour':(-0.9,0.2)}
ILLUM_MAP={'full':1.0,'three-quarter':0.75,'half':0.5,'half-shadow':0.35,'shadow':0.2,'deep-shadow':0.1}

def illum_val(v):
    if isinstance(v,str):return ILLUM_MAP.get(v,0.5)
    return float(v)

class CodeGen:
    PARAM_SCHEMA={
        'craquelure.density':(1.0,0.1,3.0),
        'sss.radius':(1.0,0.0,3.0),
        'sfumato.kernel':(1.0,0.1,5.0),
        'illumination.weight':(1.0,0.0,2.0),
        'age_shift.intensity':(1.0,0.0,3.0),
        'color_temp.offset':(0.0,-1.0,1.0),
    }
    def __init__(self,painting,param_overrides=None):
        self.painting=painting;self.pal={};self._resolve_palette()
        self.P={}
        for k,(default,lo,hi) in self.PARAM_SCHEMA.items():
            raw=(param_overrides or {}).get(k,default)
            self.P[k]=max(lo,min(hi,float(raw)))
    def _p(self,key):
        return self.P.get(key,self.PARAM_SCHEMA.get(key,(1.0,0,9))[0])
    def _resolve_palette(self):
        if not self.painting.palette:self.pal={'black':(0,0,0),'white':(1,1,1),'gray':(.5,.5,.5)};return
        raw=self.painting.palette.colors
        for nm,val in raw.items():
            if isinstance(val,PaletteColor):
                rgb=h2rgb(val.hex_value)
                if val.modifier:rgb=apply_mod(*rgb,val.modifier)
                self.pal[nm]=rgb
        for nm,val in raw.items():
            if isinstance(val,dict) and 'ref' in val:
                key=val['ref'].split('.')[-1]
                if key in self.pal:
                    rgb=self.pal[key]
                    if val.get('modifier'):rgb=apply_mod(*rgb,val['modifier'])
                    self.pal[nm]=rgb
    def resolve_color(self,val):
        if isinstance(val,PaletteColor):
            rgb=h2rgb(val.hex_value)
            if val.modifier:rgb=apply_mod(*rgb,val.modifier)
            return rgb
        if isinstance(val,dict) and 'hex' in val:return h2rgb(val['hex'])
        if isinstance(val,str):
            key=val.split('.')[-1] if '.' in val else val
            if key in self.pal:return self.pal[key]
        return(0.6,0.5,0.4)
    def cv(self,val):return v3(*self.resolve_color(val))
    def cprop(self,k,d=None):
        if self.painting.canvas:return self.painting.canvas.properties.get(k,d)
        return d
    def generate(self):return self.gen_html(self.gen_glsl())

    def gen_glsl(self):
        ground=str(self.cprop('ground','linen'))
        age_raw=self.cprop('age',0)
        age_yrs=age_raw[0] if isinstance(age_raw,tuple) else float(age_raw) if age_raw else 0
        light=str(self.cprop('light','upper-left'))
        ld=LIGHT_DIRS.get(light,(-0.707,0.707))
        gr_rgb=h2rgb(GROUND_HEX.get(ground,'c8b89a'))
        age_f=min(1.0,age_yrs/700.0)*self._p('age_shift.intensity')
        age_f=min(1.0,age_f)
        # Apply color_temp.offset to ground color
        ct=self._p('color_temp.offset')
        gr_rgb=(min(1.0,gr_rgb[0]+ct*0.06),gr_rgb[1],max(0.0,gr_rgb[2]-ct*0.06))
        pal_defs='\n'.join(f"#define PAL_{n.replace('-','_').upper()} {v3(*rgb)}" for n,rgb in self.pal.items())
        layer_fns=[];layer_calls=[]
        for lay in self.painting.layers:
            fn='lay_'+re.sub(r'[^a-zA-Z0-9]','_',lay.name)
            layer_fns.append(self.gen_layer_fn(lay,fn,ld))
            layer_calls.append(f"  result=composite(result,{fn}(uv,aspect));")
        return f"""\
precision highp float;
uniform float u_time;
uniform vec2  u_resolution;
{pal_defs}
const vec3  GROUND={v3(*gr_rgb)};
const float AGE={age_f:.5f};
const vec2  LDIR=vec2({ld[0]:.4f},{ld[1]:.4f});
const float P_CRAQ={self._p('craquelure.density'):.4f};
const float P_SSS={self._p('sss.radius'):.4f};
const float P_SFU={self._p('sfumato.kernel'):.4f};
const float P_ILLUM={self._p('illumination.weight'):.4f};
const float P_CTEMP={self._p('color_temp.offset'):.4f};

vec4 composite(vec4 b,vec4 t){{return vec4(mix(b.rgb,t.rgb,t.a),max(b.a,t.a));}}
float sdf_ellipse(vec2 p,vec2 c,vec2 r){{vec2 q=(p-c)/r;return length(q)-1.0;}}
float sdf_box(vec2 p,vec2 c,vec2 hs){{vec2 d=abs(p-c)-hs;return length(max(d,0.0))+min(max(d.x,d.y),0.0);}}
float sdf_circle(vec2 p,vec2 c,float r){{return length(p-c)-r;}}
float smin(float a,float b,float k){{float h=clamp(0.5+0.5*(b-a)/k,0.0,1.0);return mix(b,a,h)-k*h*(1.0-h);}}
float sfu(float d,float w){{w=w*P_SFU;return smoothstep(w,-w*0.5,d);}}
float hash(vec2 p){{p=fract(p*vec2(127.1,311.7));p+=dot(p,p+45.32);return fract(p.x*p.y);}}
float noise(vec2 p){{vec2 i=floor(p),f=fract(p),u=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),u.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x),u.y);}}
float fbm(vec2 p){{float v=0.0,a=0.5;for(int i=0;i<6;i++){{v+=a*noise(p);p*=2.1;a*=0.5;}}return v;}}
vec3 age_shift(vec3 c,float f){{c=mix(c,c*vec3(0.91,0.82,0.55),f*0.40);float l=dot(c,vec3(0.299,0.587,0.114));c=mix(c,vec3(l),f*0.08);c=c*(1.0-f*0.07);c+=vec3(P_CTEMP*0.06,0.0,-P_CTEMP*0.06);return clamp(c,0.0,1.0);}}
float craquelure(vec2 p,float d){{float cr=0.0,sc=6.0*d*P_CRAQ;for(int i=0;i<5;i++){{float n1=fbm(p*sc+float(i)*1.73+7.3);float n2=fbm(p*sc*0.4+float(i)*3.14+91.0);cr+=step(abs(n1-0.5)+abs(n2-0.5),0.048)*0.22;sc*=1.9;}}return clamp(cr,0.0,1.0);}}

{chr(10).join(layer_fns)}

void main(){{
  // Y-UP: uv.y=+0.5 is TOP, -0.5 is BOTTOM
  float aspect=u_resolution.x/u_resolution.y;
  vec2 uv=(gl_FragCoord.xy/u_resolution)-0.5;
  uv.x*=aspect;
  vec4 result=vec4(GROUND,1.0);
{chr(10).join(layer_calls)}
  result.rgb=age_shift(result.rgb,AGE);
  result.rgb=pow(clamp(result.rgb,0.0,1.0),vec3(1.0/2.2));
  gl_FragColor=result;
}}"""

    def gen_layer_fn(self,layer,fn,ld):
        nm=layer.name.lower()
        if any(k in nm for k in('sky','heaven','background')):body=self.gen_sky(layer,ld)
        elif any(k in nm for k in('landscape','mountain','hill','terrain')):body=self.gen_landscape(layer)
        elif any(k in nm for k in('varnish','finish','coat')):body=self.gen_varnish(layer)
        elif any(k in nm for k in('figure','portrait','person','subject','face')):body=self.gen_figure(layer,ld)
        else:body=self.gen_generic(layer)
        return f"vec4 {fn}(vec2 uv,float aspect){{\n{body}\n}}"

    def gen_sky(self,layer,ld):
        props={s.key:s.value for s in layer.statements if isinstance(s,PropertyNode)}
        zones=[s for s in layer.statements if isinstance(s,ZoneNode)]
        ct=self.cv(props.get('color-top',{'hex':'506888'}))
        cb=self.cv(props.get('color-bottom',{'hex':'a8c0c8'}))
        hz=float(props.get('horizon',0.15))
        cloud=''
        for z in zones:
            if 'cloud' in z.name:
                zp={s.key:s.value for s in z.statements if isinstance(s,PropertyNode)}
                density=float(zp.get('density',0.35))
                ch=self.cv(zp.get('highlight',{'hex':'ece8e0'}))
                cs=self.cv(zp.get('shadow',{'hex':'aaa8a0'}))
                cloud=f"""
  if(uv.y>{hz:.4f}){{
    float cn=fbm(uv*3.5+vec2(u_time*0.012,0.0));
    float cs2=fbm(uv*5.0+vec2(100.0,u_time*0.008));
    float cf=smoothstep(0.44,0.62,cn)*smoothstep(0.40,0.58,cs2);
    cf*={density:.4f}*smoothstep({hz:.4f},{hz+0.20:.4f},uv.y)*smoothstep(0.50,0.36,uv.y);
    sky_c=mix(sky_c,mix({cs},{ch},cf),cf*0.70);
  }}"""
        return f"""\
  float hz={hz:.4f};
  float t=clamp((uv.y-hz)/(0.5-hz),0.0,1.0);t=pow(t,0.7);
  vec3 sky_c=mix({cb},{ct},t);
  sky_c+=mix(sky_c*vec3(1.02,1.0,0.96)+vec3(0.05,0.04,0.02),sky_c,smoothstep(hz,hz+0.10,uv.y))*0.28;
  sky_c+=(fbm(uv*2.5)-0.5)*0.018;
  float sky_a=smoothstep(hz,hz+0.025,uv.y);
  {cloud}
  return vec4(sky_c,sky_a);"""

    def gen_landscape(self,layer):
        zones=[s for s in layer.statements if isinstance(s,ZoneNode)]
        lines=['  vec4 land=vec4(0.0);']
        for z in zones:
            zp={s.key:s.value for s in z.statements if isinstance(s,PropertyNode)}
            col=self.cv(zp.get('color',{'hex':'7a9080'}))
            dist=float(zp.get('distance',0.5))
            blur=0.022 if zp.get('sfumato',True) else 0.005
            aerial=dist*0.42
            safe=re.sub(r'[^a-zA-Z0-9]','_',z.name)
            if 'left' in z.name:xc,xs=-0.28,0.36
            elif 'right' in z.name:xc,xs=0.28,0.36
            else:xc,xs=0.0,0.58
            # Mountains appear ABOVE horizon (positive Y = up)
            peak=0.08+(1.0-dist)*0.26
            base=0.10+dist*0.06
            lines.append(f"""
  {{vec3 c_{safe}=mix({col},vec3(0.78,0.84,0.90),{aerial:.4f});
   float nx=(uv.x-{xc:.4f})/{xs:.4f};
   float mh={peak:.4f}*(1.0-nx*nx)+fbm(uv*vec2(2.8,1.0)+vec2({xc:.2f},0.0))*{peak*0.35:.4f};
   float md=({base:.4f}+mh)-uv.y;  // positive md = we are inside the mountain
   land=composite(land,vec4(c_{safe},sfu(md,{blur:.4f})));}}""")
        lines.append('  return land;')
        return'\n'.join(lines)

    def gen_varnish(self,layer):
        for s in layer.statements:
            if isinstance(s,CraquelureNode):
                dm={'none':0.0,'light':0.6,'medium':1.0,'heavy':1.8}
                dep={'micro':0.14,'shallow':0.28,'deep':0.5}
                d=dm.get(str(s.properties.get('density','medium')),1.0)
                dv=dep.get(str(s.properties.get('depth','micro')),0.14)
                return f"  float ck=craquelure(uv,{d:.4f})*{dv:.4f};\n  return vec4(vec3(0.05,0.02,0.0),ck*0.65);"
        return '  return vec4(0.0);'

    def gen_figure(self,layer,ld):
        # Y-UP layout: face at (0,+0.10), hair above, gown below
        FCX,FCY=0.0,0.10
        zones=[s for s in layer.statements if isinstance(s,ZoneNode)]
        features=[s for s in layer.statements if isinstance(s,FeatureNode)]
        skin_z=next((z for z in zones if any(k in z.name for k in('skin','face','flesh'))),None)
        hair_z=next((z for z in zones if 'hair' in z.name),None)
        gown_z=next((z for z in zones if any(k in z.name for k in('gown','dress','cloth','robe','garment'))),None)
        lines=['  vec4 fig=vec4(0.0);']
        if gown_z:lines.append(self.gen_gown(gown_z,FCX,FCY))
        if hair_z:lines.append(self.gen_hair(hair_z,FCX,FCY))
        if skin_z:lines.append(self.gen_skin(skin_z,FCX,FCY,ld))
        for feat in features:
            if feat.name=='eyes':lines.append(self.gen_eyes(feat,FCX,FCY))
            elif feat.name=='mouth':lines.append(self.gen_mouth(feat,FCX,FCY))
            elif feat.name=='nose':lines.append(self.gen_nose(feat,FCX,FCY))
        lines.append('  return fig;')
        return'\n'.join(lines)

    def gen_gown(self,zone,cx,cy):
        props={s.key:s.value for s in zone.statements if isinstance(s,PropertyNode)}
        subs=[s for s in zone.statements if isinstance(s,ZoneNode)]
        col=self.cv(props.get('color',{'hex':'1a2018'}))
        blur=0.036 if props.get('sfumato',True) else 0.010
        # Gown is BELOW face (Y-UP: lower y)
        gown_cy=cy-0.32  # gown body center
        neck_y=cy-0.04   # top of gown / bottom of neck
        sub_code=''
        for sub in subs:
            sp={s.key:s.value for s in sub.statements if isinstance(s,PropertyNode)}
            sc=self.cv(sp.get('color',{'hex':'c8a84b'}))
            if any(k in sub.name for k in('trim','gold','border')):
                trim_y=cy-0.09
                sub_code=f"""
    float trim_sdf=abs(sdf_box(uv,vec2({cx:.4f},{trim_y:.4f}),vec2(0.20,0.009)))-0.002;
    float trim_a=sfu(trim_sdf,0.004)*gown_a;
    fig=composite(fig,vec4({sc}*(0.80+sin(uv.x*28.0)*0.20),trim_a));"""
        return f"""
  {{vec3 gown_c={col}*(1.0-sin(uv.x*11.0+fbm(uv*3.2)*2.6)*0.013*0.7);
   float body=sdf_box(uv,vec2({cx:.4f},{gown_cy:.4f}),vec2(0.33,0.30));
   float shoulder=sdf_ellipse(uv,vec2({cx:.4f},{cy-0.12:.4f}),vec2(0.30,0.09));
   float neck=sdf_ellipse(uv,vec2({cx:.4f},{neck_y:.4f}),vec2(0.050,0.038));
   float gown_sdf=max(smin(body,shoulder,0.04),-neck);
   float gown_a=sfu(gown_sdf,{blur:.4f});
   fig=composite(fig,vec4(gown_c,gown_a));
   {sub_code}}}"""

    def gen_hair(self,zone,cx,cy):
        props={s.key:s.value for s in zone.statements if isinstance(s,PropertyNode)}
        col=self.cv(props.get('color',{'hex':'1a0e06'}))
        blur=0.026 if props.get('sfumato',True) else 0.010
        # Hair: crown ABOVE face (Y-UP: higher y), drapes alongside face
        crown_y=cy+0.14
        drape_y=cy-0.06  # drapes extend down past face center
        return f"""
  {{vec3 hair_c={col};
   float crown=sdf_ellipse(uv,vec2({cx:.4f},{crown_y:.4f}),vec2(0.116,0.118));
   float dl=sdf_ellipse(uv,vec2({cx-0.092:.4f},{drape_y:.4f}),vec2(0.056,0.215));
   float dr=sdf_ellipse(uv,vec2({cx+0.092:.4f},{drape_y:.4f}),vec2(0.056,0.215));
   float hair_sdf=min(crown,min(dl,dr));
   float wave=sin(uv.y*18.0+fbm(uv*5.0)*3.2)*0.006;
   float tex=fbm(uv*11.0+vec2(wave,0.0));
   hair_c*=0.58+tex*0.64;
   vec2 hd=normalize(uv-vec2({cx:.4f},{crown_y:.4f}));
   hair_c+=vec3(0.16,0.08,0.02)*pow(max(0.0,dot(hd,LDIR)),5.0)*0.25;
   fig=composite(fig,vec4(hair_c,sfu(hair_sdf,{blur:.4f})));}}"""

    def gen_skin(self,zone,cx,cy,ld):
        props={s.key:s.value for s in zone.statements if isinstance(s,PropertyNode)}
        illum=next((s for s in zone.statements if isinstance(s,IlluminateNode)),None)
        sss=next((s for s in zone.statements if isinstance(s,SSSNode)),None)
        col=self.cv(props.get('color',{'hex':'c4a07a'}))
        blur=0.019 if props.get('sfumato',True) else 0.005
        neck_cy=cy-0.180
        illum_code=self.gen_illumination(illum,ld)
        sss_code=self.gen_sss(sss)
        return f"""
  {{vec3 skin_c={col};
   float fcx={cx:.4f},fcy={cy:.4f};
   float face_sdf=sdf_ellipse(uv,vec2(fcx,fcy),vec2(0.088,0.116));
   float neck_sdf=sdf_ellipse(uv,vec2(fcx,{neck_cy:.4f}),vec2(0.032,0.060));
   float skin_sdf=min(face_sdf,neck_sdf);
   vec2 fl=(uv-vec2(fcx,fcy))/vec2(0.088,0.116);
   {illum_code}
   skin_c+=(fbm(uv*42.0)-0.5)*0.015*vec3(1.0,0.78,0.58);
   {sss_code}
   fig=composite(fig,vec4(skin_c,sfu(skin_sdf,{blur:.4f})));}}"""

    def gen_illumination(self,illum,ld):
        if not illum:
            return "float diff=dot(fl*vec2(-1.0,1.0),normalize(LDIR))*0.5+0.5;skin_c=mix(skin_c*0.52,skin_c*1.22,pow(diff,1.2));"
        r=illum.regions
        fh=illum_val(r.get('forehead','full'))
        lc=illum_val(r.get('left-cheek','three-quarter'))
        rc=illum_val(r.get('right-cheek','shadow'))
        ob=illum_val(r.get('orbital','shadow'))
        ch=illum_val(r.get('chin','shadow'))
        def m(v):return 0.36+v*0.86
        # In Y-UP face-local coords: fl.y>0 = UPPER face (forehead), fl.y<0 = LOWER face (chin)
        return f"""
   // Y-UP illuminate: fl.y>0=forehead, fl.y<0=chin
   float wf=smoothstep(0.0,0.35,fl.y)*smoothstep(0.70,0.36,abs(fl.x));
   float wlc=smoothstep(0.38,0.04,fl.y)*smoothstep(-0.04,-0.46,fl.x)*smoothstep(-0.88,-0.54,fl.y);
   float wrc=smoothstep(0.38,0.04,fl.y)*smoothstep(0.04,0.46,fl.x)*smoothstep(-0.88,-0.54,fl.y);
   float wo=smoothstep(0.12,0.54,fl.y)*smoothstep(0.56,0.26,abs(fl.x))*(1.0-wf);
   float wch=smoothstep(-0.26,-0.66,fl.y)*smoothstep(0.40,0.10,abs(fl.x));
   float tw=wf+wlc+wrc+wo+wch+0.001;
   float il=(wf*{m(fh):.4f}+wlc*{m(lc):.4f}+wrc*{m(rc):.4f}+wo*{m(ob):.4f}+wch*{m(ch):.4f})/tw;
   il=clamp(il*P_ILLUM,0.20,1.40);
   skin_c*=il;
   skin_c+=vec3(0.05,0.02,-0.01)*smoothstep(0.88,1.18,il);
   skin_c+=vec3(-0.02,-0.01,0.02)*smoothstep(0.50,0.28,il);"""

    def gen_sss(self,sss):
        if not sss:return''
        RPOS={'nose-bridge':(0.0,0.06),'cheeks':(0.35,-0.04),'temples':(0.75,0.30),'chin':(0.0,-0.62),'ears':(1.05,0.0)}
        lines=[]
        for nm,amt in sss.properties.items():
            a=amt[0] if isinstance(amt,tuple) else float(amt)
            px,py=RPOS.get(nm,(0.0,0.0));safe=nm.replace('-','_')
            lines.append(f"{{float sd=length(fl-vec2({px:.2f},{py:.2f}));float sf=smoothstep(0.30*P_SSS+0.01,0.0,sd);skin_c=mix(skin_c,mix(skin_c,vec3(0.88,0.32,0.20)*skin_c.r*1.65,0.5),{a:.4f}*sf);}}")
        return'\n   '.join(lines)

    def gen_eyes(self,feat,cx,cy):
        iris_c=self.cv(feat.properties.get('iris',{'hex':'3a281a'}))
        blur=0.006 if feat.properties.get('sfumato',True) else 0.003
        brows=feat.properties.get('brows',None)
        asym={}
        for b in feat.blocks:
            if isinstance(b,ZoneNode) and b.name=='asymmetry':
                for s in b.statements:
                    if isinstance(s,PropertyNode):asym[s.key]=s.value
        def px2(v):return(v[0] if isinstance(v,tuple) else float(v))*0.0017
        ry_off=px2(asym.get('right-eye-y',0));lx_off=px2(asym.get('left-eye-x',0))
        # Eyes sit ABOVE face center (Y-UP)
        ey=cy+0.040;ex=0.031;er=0.020;ir=er*0.63;pr=ir*0.44
        lcx=cx-ex+lx_off;lcy=ey;rcx=cx+ex;rcy=ey+ry_off
        brow_code=''
        if brows and brows!='absent':
            # Brows above eyes (Y-UP: higher y = above)
            brow_code=f"float brl=sdf_ellipse(uv,vec2({lcx:.4f},{lcy+0.019:.4f}),vec2({er*1.3:.4f},{er*0.27:.4f}));float brr=sdf_ellipse(uv,vec2({rcx:.4f},{rcy+0.019:.4f}),vec2({er*1.3:.4f},{er*0.27:.4f}));fig=composite(fig,vec4(vec3(0.1,0.05,0.02),sfu(min(brl,brr),0.004)));"
        return f"""
  {{float le_s=sdf_ellipse(uv,vec2({lcx:.4f},{lcy:.4f}),vec2({er:.4f},{er*0.62:.4f}));
   float re_s=sdf_ellipse(uv,vec2({rcx:.4f},{rcy:.4f}),vec2({er:.4f},{er*0.62:.4f}));
   float le_a=sfu(le_s,{blur:.4f}),re_a=sfu(re_s,{blur:.4f});
   fig=composite(fig,vec4(vec3(0.90,0.86,0.82),le_a));
   fig=composite(fig,vec4(vec3(0.90,0.86,0.82),re_a));
   vec3 iris_col={iris_c};
   float li_s=sdf_circle(uv,vec2({lcx:.4f},{lcy-0.001:.4f}),{ir:.4f});
   float ri_s=sdf_circle(uv,vec2({rcx:.4f},{rcy-0.001:.4f}),{ir:.4f});
   float li_a=sfu(li_s,0.003)*le_a,ri_a=sfu(ri_s,0.003)*re_a;
   iris_col+=vec3(0.04,0.02,0.0)*smoothstep({ir:.4f},0.0,length(uv-vec2({lcx:.4f},{lcy:.4f})));
   fig=composite(fig,vec4(iris_col,li_a));fig=composite(fig,vec4(iris_col,ri_a));
   float lp=sdf_circle(uv,vec2({lcx:.4f},{lcy:.4f}),{pr:.4f});
   float rp=sdf_circle(uv,vec2({rcx:.4f},{rcy:.4f}),{pr:.4f});
   fig=composite(fig,vec4(vec3(0.05,0.03,0.02),sfu(min(lp,rp),0.002)));
   fig=composite(fig,vec4(vec3(0.12,0.06,0.04),smoothstep(0.006,0.001,min(abs(le_s),abs(re_s)))*0.72));
   {brow_code}}}"""

    def gen_mouth(self,feat,cx,cy):
        col=self.cv(feat.properties.get('color',{'hex':'b05548'}))
        expression=str(feat.properties.get('expression','neutral'))
        blur=0.006 if feat.properties.get('sfumato',True) else 0.002
        asym={}
        for b in feat.blocks:
            if isinstance(b,ZoneNode) and b.name=='asymmetry':
                for s in b.statements:
                    if isinstance(s,PropertyNode):asym[s.key]=s.value
        def px2(v):return(v[0] if isinstance(v,tuple) else float(v))*0.0012
        lc_off=px2(asym.get('left-corner',0));rc_off=px2(asym.get('right-corner',0))
        # Mouth BELOW face center (Y-UP: lower y)
        mcy=cy-0.058;mw=0.027;mh=0.011
        smile=0.0
        if expression=='smile':smile=0.55
        elif expression=='frown':smile=-0.55
        elif expression=='ambiguous':smile=0.08
        return f"""
  {{vec3 lip_c={col};
   float mcx={cx:.4f},mcy={mcy:.4f};
   float ul=sdf_ellipse(uv,vec2(mcx,mcy+{mh*0.32:.4f}),vec2({mw:.4f},{mh*0.72:.4f}));
   float ll=sdf_ellipse(uv,vec2(mcx,mcy-{mh*0.25:.4f}),vec2({mw*1.1:.4f},{mh:.4f}));
   float corner=(uv.x-mcx)*{smile:.4f}*0.28+(uv.x<mcx?{lc_off:.5f}:{rc_off:.5f});
   float lip_a=sfu(min(ul,ll)+corner,{blur:.4f});
   lip_c=mix(lip_c*0.66,lip_c*1.10,smoothstep(-0.003,0.004,uv.y-mcy));
   fig=composite(fig,vec4(lip_c,lip_a));
   float inx=smoothstep({mw:.4f},{mw*0.72:.4f},abs(uv.x-mcx));
   fig=composite(fig,vec4(lip_c*0.36+vec3(0.05,0.0,0.0),smoothstep(0.003,0.0,abs(min(ul,ll)+corner+0.001))*inx*0.82));}}"""

    def gen_nose(self,feat,cx,cy):
        bsharp=0.88 if str(feat.properties.get('bridge','defined'))=='defined' else 0.45
        # Nose between eyes and mouth (Y-UP)
        ncy=cy-0.010
        return f"""
  {{float ncx={cx:.4f},ncy={ncy:.4f};
   float nl=sdf_ellipse(uv,vec2(ncx-0.012,ncy-0.026),vec2(0.009,0.007));
   float nr=sdf_ellipse(uv,vec2(ncx+0.012,ncy-0.026),vec2(0.009,0.007));
   fig=composite(fig,vec4(vec3(0.0),sfu(min(nl,nr),0.006)*0.44));
   float br=sdf_box(uv,vec2(ncx,ncy+0.010),vec2(0.005,0.034));
   fig=composite(fig,vec4(vec3(0.94,0.80,0.62),smoothstep(0.007,0.0,abs(br))*{bsharp:.4f}*0.20));}}"""

    def gen_generic(self,layer):
        props={s.key:s.value for s in layer.statements if isinstance(s,PropertyNode)}
        col=self.cv(props.get('color',{'hex':'a0a0a0'}))
        return f'  return vec4({col},1.0);'

    def gen_html(self,glsl):
        title=str(self.cprop('title','PIGMENT Painting')).strip('"\'')
        artist=str(self.cprop('artist','')).strip('"\'')
        date_v=self.cprop('date','')
        date=str(date_v).strip('"\'') if date_v else ''
        ratio_v=self.cprop('ratio',None);res_v=self.cprop('resolution',None)
        if isinstance(res_v,dict) and 'resolution' in res_v:nat_w,nat_h=res_v['resolution']
        elif isinstance(ratio_v,dict) and 'ratio' in ratio_v:nat_w,nat_h=ratio_v['ratio']
        else:nat_w,nat_h=53,77
        max_d=700
        if nat_w>nat_h:dw,dh=max_d,max(int(max_d*nat_h/nat_w),1)
        else:dh,dw=max_d,max(int(max_d*nat_w/nat_h),1)
        swatches=''.join(f'<span class="sw" title="{n}" style="background:#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"></span>' for n,(r,g,b) in list(self.pal.items())[:20])
        glsl_js=glsl.replace('\\','\\\\').replace('`','\\`').replace('${','$\\{')
        attr=''
        if artist:attr+=f'<div class="sub">{artist}</div>'
        if date:attr+=f'<div class="sub">{date}</div>'
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{title}</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0e0d09;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:Georgia,serif;color:#c8b898;padding:24px}}
.frame{{border:22px solid #1e1508;box-shadow:0 0 0 2px #8a6828,0 0 0 4px #1e1508,inset 0 0 24px rgba(0,0,0,.6),0 16px 70px rgba(0,0,0,.95);position:relative;margin-bottom:22px}}
.frame::before{{content:'';position:absolute;inset:-10px;border:2px solid #a07838;pointer-events:none}}
canvas{{display:block}}.info{{text-align:center;max-width:{dw}px}}
h1{{font-style:italic;font-size:1.65em;color:#eadab0;margin-bottom:5px;letter-spacing:.02em}}
.sub{{font-size:.84em;color:#7a6848;margin:2px 0}}
.palette{{display:flex;flex-wrap:wrap;gap:5px;justify-content:center;margin:12px 0}}
.sw{{width:17px;height:17px;border-radius:50%;border:1px solid #3a2818;display:inline-block}}
.tech{{font-size:.72em;color:#4a3828;font-family:monospace;margin-top:8px;letter-spacing:.04em}}
#err{{color:#ff5030;font-family:monospace;font-size:.8em;max-width:660px;white-space:pre-wrap;padding:10px;margin-top:10px}}
</style></head><body>
<div class="frame"><canvas id="c" width="{dw}" height="{dh}"></canvas></div>
<div class="info"><h1>{title}</h1>{attr}<div class="palette">{swatches}</div>
<div class="tech">PIGMENT v3.0 &nbsp;·&nbsp; WebGL &nbsp;·&nbsp; {dw}×{dh} &nbsp;·&nbsp; 60 fps</div></div>
<div id="err"></div>
<script>
const canvas=document.getElementById('c');
const gl=canvas.getContext('webgl')||canvas.getContext('experimental-webgl');
const err=document.getElementById('err');
if(!gl){{err.textContent='WebGL not supported.';}}
const VS=`attribute vec2 a;void main(){{gl_Position=vec4(a,0,1);}}`;
const FS=`{glsl_js}`;
function mkS(t,src){{const s=gl.createShader(t);gl.shaderSource(s,src);gl.compileShader(s);return gl.getShaderParameter(s,gl.COMPILE_STATUS)?{{s}}:{{e:gl.getShaderInfoLog(s)}};}}
const vr=mkS(gl.VERTEX_SHADER,VS);
if(vr.e){{err.textContent='VS: '+vr.e;}}else{{
const fr=mkS(gl.FRAGMENT_SHADER,FS);
if(fr.e){{err.textContent='FS:\\n'+fr.e;}}else{{
const p=gl.createProgram();gl.attachShader(p,vr.s);gl.attachShader(p,fr.s);gl.linkProgram(p);
if(!gl.getProgramParameter(p,gl.LINK_STATUS)){{err.textContent='Link: '+gl.getProgramInfoLog(p);}}
else{{gl.useProgram(p);
const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);
gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
const pos=gl.getAttribLocation(p,'a');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
const uT=gl.getUniformLocation(p,'u_time'),uR=gl.getUniformLocation(p,'u_resolution');
gl.uniform2f(uR,canvas.width,canvas.height);
const t0=performance.now();
(function f(){{gl.uniform1f(uT,(performance.now()-t0)/1000);gl.drawArrays(gl.TRIANGLES,0,6);requestAnimationFrame(f);
}})();}}}}}}
</script></body></html>"""

# ─────────────────────────────────────────────────────────────────
# EVOLUTIONARY PAINTER HTML
# ─────────────────────────────────────────────────────────────────

def gen_evolve_html(demo_image_path=None):
    demo_hint=''
    demo_script=''
    if demo_image_path and os.path.exists(demo_image_path):
        ext=os.path.splitext(demo_image_path)[1].lower().lstrip('.')
        mime={'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}.get(ext,'image/jpeg')
        with open(demo_image_path,'rb') as f:b64=base64.b64encode(f.read()).decode('ascii')
        name=os.path.basename(demo_image_path)
        demo_hint=f'<div style="margin-top:8px;font-size:.75em;opacity:.5">Pre-loaded: {name}</div>'
        demo_script=f"(function(){{loadImageFromURL('data:{mime};base64,{b64}');}})();"
    else:
        demo_hint='<div style="margin-top:8px;font-size:.75em;opacity:.4">Try any portrait or landscape</div>'

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PIGMENT — Evolutionary Painter</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#080806;color:#c0b898;font-family:'Courier New',monospace;
     min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px;gap:14px}
h1{font-family:Georgia,serif;font-style:italic;font-size:1.55em;color:#e8d898;letter-spacing:.04em}
.sub{font-size:.7em;color:#44402e;letter-spacing:.08em}
#dropzone{border:2px dashed #3a3828;border-radius:8px;padding:28px 44px;text-align:center;
  cursor:pointer;color:#5a5440;font-size:.83em;transition:all .2s}
#dropzone.over,#dropzone:hover{border-color:#b89838;color:#d8c878;background:rgba(184,152,56,.04)}
.controls{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;align-items:center}
button{background:#141210;border:1px solid #3a3828;color:#b8a878;padding:6px 16px;
  border-radius:4px;cursor:pointer;font-family:inherit;font-size:.8em;letter-spacing:.04em;transition:all .15s}
button:hover{background:#1e1c14;border-color:#7a6830;color:#d8c878}
button:disabled{opacity:.35;cursor:not-allowed}
button.go{background:#1a1808;border-color:#c8a838;color:#e8d080}
button.go:hover{background:#242010}
select,input[type=range]{background:#141210;border:1px solid #3a3828;color:#b8a878;
  padding:5px 8px;border-radius:4px;font-family:inherit;font-size:.78em}
label{font-size:.76em;color:#5a5440;display:flex;align-items:center;gap:6px}
.panels{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.panel{display:flex;flex-direction:column;align-items:center;gap:5px}
.plabel{font-size:.65em;color:#3a3828;letter-spacing:.09em;text-transform:uppercase}
canvas.view{border:1px solid #1e1c14;image-rendering:pixelated;image-rendering:crisp-edges}
.stats{display:flex;gap:20px;flex-wrap:wrap;justify-content:center;font-size:.76em;color:#7a7460}
.sv{font-size:1.28em;color:#c0b080;font-family:Georgia,serif}
.sl{font-size:.67em;color:#3a3828;letter-spacing:.06em}
#crv{background:#0a0a08;border:1px solid #1e1c14;border-radius:3px;width:460px;max-width:96vw;height:72px}
.expbox{background:#0c0c0a;border:1px solid #1e1c14;border-radius:6px;padding:12px 16px;width:460px;max-width:96vw}
.expbox h3{font-family:Georgia,serif;font-size:.85em;color:#7a6840;margin-bottom:8px;letter-spacing:.04em}
#pg-out{width:100%;height:150px;background:#080806;border:1px solid #181612;color:#908860;
  font-family:'Courier New',monospace;font-size:.7em;padding:8px;resize:vertical;outline:none}
.row{display:flex;gap:8px;margin-top:8px}
</style>
</head>
<body>
<h1>PIGMENT — Evolutionary Painter</h1>
<div class="sub">ROGER ALSING HILL-CLIMBING · PIGMENT V3 · SEMI-TRANSPARENT POLYGON GENOME</div>

<div id="dropzone" onclick="document.getElementById('fi').click()">
  <div style="font-size:1.6em;margin-bottom:6px">🎨</div>
  <div>Drop target image or click to choose</div>
  """ + demo_hint + """
</div>
<input type="file" id="fi" accept="image/*" style="display:none">

<div class="controls">
  <button class="go" id="bstart" disabled onclick="doStart()">▶ Start</button>
  <button id="bpause" disabled onclick="doPause()">⏸ Pause</button>
  <button id="breset" disabled onclick="doReset()">↺ Reset</button>
  <span style="width:1px;height:22px;background:#1e1c14"></span>
  <label>Polygons
    <select id="selpoly"><option value="50" selected>50</option><option value="100">100</option><option value="150">150</option><option value="200">200</option></select>
  </label>
  <label>Speed
    <select id="selspd"><option value="10">Slow (10)</option><option value="30" selected>Normal (30)</option><option value="80">Fast (80)</option><option value="200">Max (200)</option></select>
  </label>
  <label>Max size <input type="range" id="rsize" min="2" max="9" step=".5" value="4" style="width:80px"></label>
</div>

<div class="panels">
  <div class="panel"><div class="plabel">Target</div><canvas class="view" id="cvt"></canvas></div>
  <div class="panel"><div class="plabel">Evolved</div><canvas class="view" id="cve"></canvas></div>
  <div class="panel"><div class="plabel">Diff ×4</div><canvas class="view" id="cvd"></canvas></div>
</div>

<div class="stats">
  <div><div class="sv" id="sg">0</div><div class="sl">Generation</div></div>
  <div><div class="sv" id="sf">0.00%</div><div class="sl">Fitness</div></div>
  <div><div class="sv" id="si">0</div><div class="sl">Improvements</div></div>
  <div><div class="sv" id="sr">0/s</div><div class="sl">Mut/sec</div></div>
  <div><div class="sv" id="sm">1.00</div><div class="sl">Mut rate</div></div>
</div>

<canvas id="crv"></canvas>

<div class="expbox">
  <h3>PIGMENT Genome Export</h3>
  <textarea id="pg-out" readonly placeholder="Evolve first — genome will appear as PIGMENT .pg source..."></textarea>
  <div class="row">
    <button onclick="doExport()">↓ Export .pg</button>
    <button onclick="doCopy()">Copy</button>
    <button onclick="doSaveImg()">Save PNG</button>
    <button onclick="document.getElementById('pg-out').value=genPG()">Refresh</button>
  </div>
</div>

<script>
// ── Constants ──────────────────────────────────────────────────
const BASE_W=200, BASE_H=300;
let W=BASE_W, H=BASE_H;
let targetPx=null;
let polys=[], bestPolys=[], bestErr=Infinity;
let running=false, paused=false;
let gen=0, impr=0, mutRate=1.0;
let rateT={n:0,t:performance.now()};
let fitHist=[];
let raf=null;

const cvWork=document.createElement('canvas');
const ctxWork=cvWork.getContext('2d');
const cvT=document.getElementById('cvt'),ctxT=cvT.getContext('2d');
const cvE=document.getElementById('cve'),ctxE=cvE.getContext('2d');
const cvD=document.getElementById('cvd'),ctxD=cvD.getContext('2d');
const crv=document.getElementById('crv'),crvCtx=crv.getContext('2d');
const DS=2; // display scale

// ── Image loading ──────────────────────────────────────────────
function loadFile(f){const r=new FileReader();r.onload=e=>loadURL(e.target.result);r.readAsDataURL(f);}
function loadURL(url){
  const img=new Image();
  img.onload=()=>{
    const ratio=img.height/img.width;
    W=BASE_W; H=Math.max(40,Math.round(W*ratio));
    if(H>360){H=360;W=Math.round(H/ratio);}
    cvWork.width=W;cvWork.height=H;
    ctxWork.drawImage(img,0,0,W,H);
    targetPx=new Uint8ClampedArray(ctxWork.getImageData(0,0,W,H).data);
    const dw=W*DS,dh=H*DS;
    [cvT,cvE,cvD].forEach(c=>{c.width=dw;c.height=dh;});
    ctxT.drawImage(cvWork,0,0,dw,dh);
    document.getElementById('dropzone').style.display='none';
    document.getElementById('bstart').disabled=false;
    document.getElementById('breset').disabled=false;
    doReset();
  };
  img.src=url;
}

// ── Genome ─────────────────────────────────────────────────────
function rPoly(){
  const sz=W*(0.05+Math.random()*parseFloat(document.getElementById('rsize').value)*0.06);
  const cx=Math.random()*W, cy=Math.random()*H;
  const pts=[];
  for(let i=0;i<3;i++){const a=(i/3)*Math.PI*2+Math.random()*1.2,r=sz*(0.4+Math.random()*0.9);pts.push([cx+Math.cos(a)*r,cy+Math.sin(a)*r]);}
  return{pts,r:Math.random()*255|0,g:Math.random()*255|0,b:Math.random()*255|0,a:(20+Math.random()*100)|0};
}
function clp(x,y){return[Math.max(-W*.1,Math.min(W*1.1,x)),Math.max(-H*.1,Math.min(H*1.1,y))];}
function gauss(s){const u1=Math.random(),u2=Math.random();return s*Math.sqrt(-2*Math.log(u1+1e-9))*Math.cos(2*Math.PI*u2);}

function mutPoly(p,mr){
  const q={pts:p.pts.map(pt=>[...pt]),r:p.r,g:p.g,b:p.b,a:p.a};
  const c=Math.random();
  if(c<0.28){const vi=Math.random()*q.pts.length|0;const s=W*0.05*mr;q.pts[vi]=clp(q.pts[vi][0]+gauss(s),q.pts[vi][1]+gauss(s));}
  else if(c<0.46){const dx=gauss(W*.04*mr),dy=gauss(H*.04*mr);q.pts=q.pts.map(([x,y])=>clp(x+dx,y+dy));}
  else if(c<0.62){const ch=['r','g','b'][Math.random()*3|0];q[ch]=Math.max(0,Math.min(255,q[ch]+gauss(18*mr)|0));}
  else if(c<0.78){q.a=Math.max(6,Math.min(165,q.a+gauss(10*mr)|0));}
  else if(c<0.90){const sc=0.82+Math.random()*0.40,cx=q.pts.reduce((s,p)=>s+p[0],0)/q.pts.length,cy=q.pts.reduce((s,p)=>s+p[1],0)/q.pts.length;q.pts=q.pts.map(([x,y])=>clp(cx+(x-cx)*sc,cy+(y-cy)*sc));}
  else return rPoly();
  return q;
}

// ── Render ─────────────────────────────────────────────────────
function render(ps,ctx,w,h){
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);
  for(const p of ps){
    ctx.beginPath();ctx.moveTo(p.pts[0][0],p.pts[0][1]);
    for(let i=1;i<p.pts.length;i++)ctx.lineTo(p.pts[i][0],p.pts[i][1]);
    ctx.closePath();ctx.fillStyle=`rgba(${p.r},${p.g},${p.b},${p.a/255})`;ctx.fill();
  }
}

// ── Fitness ─────────────────────────────────────────────────────
function calcErr(id){
  const d=id.data,t=targetPx;let e=0;
  for(let i=0;i<d.length;i+=4){const dr=d[i]-t[i],dg=d[i+1]-t[i+1],db=d[i+2]-t[i+2];e+=dr*dr+dg*dg+db*db;}
  return e;
}
function fitPct(e){return Math.max(0,100*(1-e/(255*255*3*W*H)));}

// ── Evolution ──────────────────────────────────────────────────
function evolveStep(){
  const pc=parseInt(document.getElementById('selpoly').value);
  const sp=parseInt(document.getElementById('selspd').value);
  for(let s=0;s<sp;s++){
    const idx=Math.random()*polys.length|0;
    const candidate=polys.slice();candidate[idx]=mutPoly(polys[idx],mutRate);
    cvWork.width=W;cvWork.height=H;render(candidate,ctxWork,W,H);
    const err=calcErr(ctxWork.getImageData(0,0,W,H));
    if(err<bestErr){
      polys=candidate;
      bestPolys=candidate.map(p=>({...p,pts:p.pts.map(pt=>[...pt])}));
      bestErr=err;impr++;
      mutRate=Math.max(0.18,mutRate*0.9999);
    }else{mutRate=Math.min(2.2,mutRate*1.00005);}
    gen++;rateT.n++;
  }
  if(polys.length<pc && gen%900===0){polys.push(rPoly());bestPolys=polys.map(p=>({...p,pts:p.pts.map(pt=>[...pt])}));}
}

let fc=0;
function frame(){
  if(!running||paused){raf=null;return;}
  evolveStep();fc++;
  if(fc%4===0)updateDisplay();
  raf=requestAnimationFrame(frame);
}

function updateDisplay(){
  cvWork.width=W;cvWork.height=H;render(bestPolys,ctxWork,W,H);
  const dw=W*DS,dh=H*DS;
  ctxE.drawImage(cvWork,0,0,dw,dh);
  // Diff
  const ev=ctxWork.getImageData(0,0,W,H);
  const diff=ctxD.createImageData(W,H);
  for(let i=0;i<ev.data.length;i+=4){
    diff.data[i]=Math.min(255,Math.abs(ev.data[i]-targetPx[i])*4);
    diff.data[i+1]=Math.min(255,Math.abs(ev.data[i+1]-targetPx[i+1])*4);
    diff.data[i+2]=Math.min(255,Math.abs(ev.data[i+2]-targetPx[i+2])*4);
    diff.data[i+3]=255;
  }
  const tmp=document.createElement('canvas');tmp.width=W;tmp.height=H;
  tmp.getContext('2d').putImageData(diff,0,0);ctxD.drawImage(tmp,0,0,dw,dh);
  // Stats
  const fp=fitPct(bestErr);
  document.getElementById('sg').textContent=gen.toLocaleString();
  document.getElementById('sf').textContent=fp.toFixed(2)+'%';
  document.getElementById('si').textContent=impr.toLocaleString();
  document.getElementById('sm').textContent=mutRate.toFixed(3);
  const now=performance.now(),dt=(now-rateT.t)/1000;
  if(dt>0.5){document.getElementById('sr').textContent=(rateT.n/dt|0)+'/s';rateT={n:0,t:now};}
  fitHist.push(fp);if(fitHist.length>300)fitHist.shift();
  drawCurve();
  if(impr>0&&impr%3000===0)document.getElementById('pg-out').value=genPG();
}

function drawCurve(){
  const cw=crv.width,ch=crv.height;crvCtx.clearRect(0,0,cw,ch);
  if(fitHist.length<2)return;
  const mx=Math.max(...fitHist),mn=Math.min(...fitHist),rng=Math.max(mx-mn,0.5);
  crvCtx.strokeStyle='#c0a030';crvCtx.lineWidth=1.5;crvCtx.beginPath();
  for(let i=0;i<fitHist.length;i++){
    const x=(i/(fitHist.length-1))*cw,y=ch-((fitHist[i]-mn)/rng)*(ch-4)-2;
    i===0?crvCtx.moveTo(x,y):crvCtx.lineTo(x,y);
  }
  crvCtx.stroke();
  crvCtx.fillStyle='#3a3828';crvCtx.font='10px Courier New';
  crvCtx.fillText(mx.toFixed(1)+'%',4,11);crvCtx.fillText(mn.toFixed(1)+'%',4,ch-3);
}

// ── Controls ───────────────────────────────────────────────────
function doStart(){if(!targetPx)return;running=true;paused=false;document.getElementById('bstart').disabled=true;document.getElementById('bpause').disabled=false;if(!raf)raf=requestAnimationFrame(frame);}
function doPause(){paused=!paused;document.getElementById('bpause').textContent=paused?'▶ Resume':'⏸ Pause';if(!paused&&!raf)raf=requestAnimationFrame(frame);}
function doReset(){
  if(raf){cancelAnimationFrame(raf);raf=null;}running=false;paused=false;
  const pc=parseInt(document.getElementById('selpoly').value);
  polys=Array.from({length:pc},()=>rPoly());
  bestPolys=polys.map(p=>({...p,pts:p.pts.map(pt=>[...pt])}));
  cvWork.width=W;cvWork.height=H;render(bestPolys,ctxWork,W,H);
  bestErr=calcErr(ctxWork.getImageData(0,0,W,H));
  gen=0;impr=0;mutRate=1.0;fitHist=[];rateT={n:0,t:performance.now()};
  document.getElementById('bstart').disabled=false;
  document.getElementById('bpause').disabled=true;
  document.getElementById('bpause').textContent='⏸ Pause';
  document.getElementById('pg-out').value='';
  updateDisplay();
}

// ── Genome export ──────────────────────────────────────────────
function genPG(){
  const fp=fitPct(bestErr);
  const lines=[
    `-- PIGMENT v3 Evolutionary Genome`,
    `-- Gen: ${gen.toLocaleString()}  Fitness: ${fp.toFixed(2)}%  Polygons: ${bestPolys.length}`,
    `-- Algorithm: Roger Alsing hill-climbing mutation`,``,
    `canvas { format: portrait  title: "Evolved Painting"  artist: "PIGMENT v3 Evolutionary Engine"  date: "${new Date().getFullYear()}" }`,``,
    `palette {`,
  ];
  const step=Math.max(1,bestPolys.length/16|0);
  const palNames=[];
  for(let i=0;i<bestPolys.length;i+=step){
    const p=bestPolys[i];
    const h=p.r.toString(16).padStart(2,'0')+p.g.toString(16).padStart(2,'0')+p.b.toString(16).padStart(2,'0');
    const nm=`p${palNames.length}`;palNames.push(nm);
    lines.push(`  ${nm.padEnd(8)}: #${h}`);
  }
  lines.push(`}`,'',`layer evolved {`);
  for(let i=0;i<bestPolys.length;i++){
    const p=bestPolys[i];
    const h=p.r.toString(16).padStart(2,'0')+p.g.toString(16).padStart(2,'0')+p.b.toString(16).padStart(2,'0');
    const op=(p.a/255).toFixed(3);
    const pts=p.pts.map(([x,y])=>`${(x/W).toFixed(3)},${(y/H).toFixed(3)}`).join(' ');
    lines.push(`  -- [${pts}]  α=${op}`);
    lines.push(`  zone poly-${i} { color: #${h}  opacity: ${op} }`);
  }
  lines.push(`}`);return lines.join('\n');
}
function doExport(){const t=genPG();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/plain'}));a.download=`evolved_gen${gen}.pg`;a.click();document.getElementById('pg-out').value=t;}
function doCopy(){navigator.clipboard.writeText(genPG()).catch(()=>{});document.getElementById('pg-out').value=genPG();}
function doSaveImg(){cvWork.width=W*4;cvWork.height=H*4;render(bestPolys,ctxWork,W*4,H*4);const a=document.createElement('a');a.href=cvWork.toDataURL('image/png');a.download=`evolved_gen${gen}.png`;a.click();}

// ── File drop ──────────────────────────────────────────────────
document.getElementById('fi').onchange=e=>{if(e.target.files[0])loadFile(e.target.files[0]);};
const dz=document.getElementById('dropzone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('over');});
dz.addEventListener('dragleave',()=>dz.classList.remove('over'));
dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('over');const f=e.dataTransfer.files[0];if(f&&f.type.startsWith('image/'))loadFile(f);});

// Curve resize
function rCrv(){crv.width=document.getElementById('crv').parentElement.clientWidth||460;crv.height=72;}
rCrv();window.addEventListener('resize',rCrv);

// Demo pre-load
""" + demo_script + """
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────
DEMO_PG = """\
-- mona_lisa.pg — La Gioconda in PIGMENT v3 (Y-UP coordinate system)
canvas {
  format:   portrait
  ratio:    77:53
  ground:   poplar
  age:      500yr
  light:    upper-left
  title:    "Mona Lisa"
  artist:   "Leonardo da Vinci (described in PIGMENT)"
  date:     "c.1503-1519 / 2025"
}
palette {
  skin-lit:      warm #e8c9a0
  skin-mid:           #c4a07a
  skin-shadow:   cool #7a5035
  gown-dark:          #0f1a0c
  gown-lit:           #1e3818
  gold-trim:          #c8a84b
  sky-top:       cool #607898
  sky-horizon:        #b8ccd4
  mountain-far:       #8faab2
  mountain-near:      #c8d8d5
  hair-dark:          #1a0e06
  hair-auburn:        #5a2e10
  iris-dark:          #3a281a
  lip-rose:           #b55a4a
}
layer sky {
  fill: aerial-gradient
  horizon: 0.15
  color-top:    palette.sky-top
  color-bottom: palette.sky-horizon
  zone clouds {
    density: 0.32
    highlight: palette.sky-horizon
    shadow: palette.mountain-far
    sfumato: true
  }
}
layer landscape {
  zone mountains-left {
    color: palette.mountain-far
    distance: 0.75
    sfumato: true
  }
  zone mountains-right {
    color: palette.mountain-near
    distance: 0.42
    sfumato: true
  }
}
layer figure {
  zone gown {
    color: palette.gown-dark
    sfumato: true
    zone trim {
      color: palette.gold-trim
    }
  }
  zone hair {
    color: palette.hair-dark
    sfumato: true
  }
  zone skin {
    color: palette.skin-mid
    sfumato: true
    illuminate {
      forehead:    full
      left-cheek:  three-quarter
      right-cheek: half-shadow
      orbital:     shadow
      chin:        shadow
    }
    sss {
      nose-bridge: 0.22
      cheeks:      0.14
      temples:     0.08
    }
  }
  feature eyes {
    iris: palette.iris-dark
    sfumato: true
    brows: absent
    asymmetry { right-eye-y: -2px }
  }
  feature mouth {
    color: palette.lip-rose
    expression: ambiguous
    sfumato: true
    asymmetry { left-corner: +1px  right-corner: -1px }
  }
  feature nose {
    bridge: defined
    sfumato: true
  }
  sfumato boundary {
    blur: graduated
    warmth: 0.15
  }
}
layer varnish {
  craquelure {
    substrate: canvas.ground
    density: medium
    depth: micro
  }
}
"""

def print_ast(node,indent=0):
    pad='  '*indent
    if isinstance(node,PaintingNode):
        print(f"{pad}PaintingNode")
        if node.canvas:print_ast(node.canvas,indent+1)
        if node.palette:print_ast(node.palette,indent+1)
        for l in node.layers:print_ast(l,indent+1)
    elif isinstance(node,CanvasNode):print(f"{pad}CanvasNode {node.properties}")
    elif isinstance(node,PaletteNode):
        print(f"{pad}PaletteNode ({len(node.colors)} colors)")
        for k,v in node.colors.items():print(f"{pad}  {k}: {v}")
    elif isinstance(node,LayerNode):
        print(f"{pad}LayerNode '{node.name}'")
        for s in node.statements:print_ast(s,indent+1)
    elif isinstance(node,ZoneNode):
        print(f"{pad}ZoneNode '{node.name}'")
        for s in node.statements:print_ast(s,indent+1)
    elif isinstance(node,FeatureNode):print(f"{pad}FeatureNode '{node.name}' {node.properties}")
    elif isinstance(node,IlluminateNode):print(f"{pad}IlluminateNode {node.regions}")
    elif isinstance(node,SSSNode):print(f"{pad}SSSNode {node.properties}")
    elif isinstance(node,CraquelureNode):print(f"{pad}CraquelureNode {node.properties}")
    elif isinstance(node,PropertyNode):print(f"{pad}PropertyNode {node.key}: {node.value!r}")
    else:print(f"{pad}{type(node).__name__}")

def main():
    ap=argparse.ArgumentParser(description='PIGMENT Language Compiler v3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="python pigment.py --demo          # Mona Lisa\npython pigment.py --evolve          # Evolutionary painter\npython pigment.py --evolve img.jpg  # Evolve toward image")
    ap.add_argument('file',nargs='?',help='.pg source file')
    ap.add_argument('-o','--output',help='Output HTML file')
    ap.add_argument('--demo',action='store_true',help='Compile built-in Mona Lisa')
    ap.add_argument('--evolve',nargs='?',const='',metavar='IMAGE',help='Generate evolutionary painter')
    ap.add_argument('--tokens',action='store_true');ap.add_argument('--ast',action='store_true');ap.add_argument('--glsl',action='store_true')
    ap.add_argument('--param',action='append',metavar='KEY=VALUE',dest='params',
        help='Override a render parameter (repeatable). Keys: craquelure.density, sss.radius, sfumato.kernel, illumination.weight, age_shift.intensity, color_temp.offset. E.g. --param craquelure.density=0.8 --param sss.radius=0.4')
    args=ap.parse_args()

    if args.evolve is not None:
        img=args.evolve if args.evolve else None
        html=gen_evolve_html(img)
        out=args.output or 'pigment_evolve.html'
        with open(out,'w',encoding='utf-8') as f:f.write(html)
        print(f"[PIGMENT] ✓ Evolutionary painter → {out}")
        if img:print(f"          Pre-loaded: {img}")
        print(f"          Open {out} in a browser · drop any image · press Start")
        return

    if args.demo:source=DEMO_PG;default_out='mona_lisa.html'
    elif args.file:
        try:
            with open(args.file,encoding='utf-8') as f:source=f.read()
        except FileNotFoundError:print(f"[Error] Not found: {args.file}",file=sys.stderr);sys.exit(1)
        default_out=os.path.splitext(args.file)[0]+'.html'
    else:ap.print_help();sys.exit(0)

    try:tokens=Lexer(source).tokenize()
    except LexError as e:print(e,file=sys.stderr);sys.exit(1)
    if args.tokens:[print(t) for t in tokens];return

    try:painting=Parser(tokens).parse()
    except ParseError as e:print(e,file=sys.stderr);sys.exit(1)
    if args.ast:print_ast(painting);return

    overrides={}
    for p in (args.params or []):
        if '=' not in p:print(f"[Error] --param must be KEY=VALUE, got: {p}",file=sys.stderr);sys.exit(1)
        k,v=p.split('=',1)
        try:overrides[k.strip()]=float(v.strip())
        except ValueError:print(f"[Error] --param value must be numeric, got: {v}",file=sys.stderr);sys.exit(1)
    gen=CodeGen(painting,param_overrides=overrides);glsl=gen.gen_glsl()
    if args.glsl:print(glsl);return

    html=gen.gen_html(glsl);out=args.output or default_out
    with open(out,'w',encoding='utf-8') as f:f.write(html)
    print(f"[PIGMENT] ✓ Compiled → {out}")
    print(f"          {len(source.splitlines())} lines .pg → {len(glsl.splitlines())} lines GLSL → {len(html):,} bytes HTML")
    if painting.palette:print(f"          {len(painting.palette.colors)} colors · {len(painting.layers)} layers")

if __name__=='__main__':main()
