import React from 'react';
import {AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Palabra = {texto: string; inicio: number; fin: number; resalte?: boolean};
export type Grupo = {inicio: number; fin: number; palabras: Palabra[]};
export type Estilo = {
  fuente: string;
  tam_px: number;
  color: string;
  color_activo: string;
  fondo: string;
  y_pct: number; // centro vertical de la caja, en fraccion del alto
  mayusculas: boolean;
  zoom_gancho: number; // 1 = sin zoom
  zona?: {arriba: number; abajo: number; izquierda: number; derecha: number}; // zona segura en px
};
export type ReelProps = {
  video: string; // archivo dentro de --public-dir
  duracion_s: number;
  fps?: number;
  ancho?: number;
  alto?: number;
  subtitulos: Grupo[];
  ganchos: {inicio: number; fin: number; texto: string}[];
  estilo: Estilo;
};

export const propsPorDefecto: ReelProps = {
  video: 'editado.mp4',
  duracion_s: 1,
  subtitulos: [],
  ganchos: [],
  estilo: {fuente: 'Arial Black', tam_px: 76, color: '#FFFFFF', color_activo: '#FFD400', fondo: '#FF2D78',
    y_pct: 0.68, mayusculas: true, zoom_gancho: 1.08},
};

const Subtitulo: React.FC<{g: Grupo; e: Estilo; t: number}> = ({g, e, t}) => {
  const {height} = useVideoConfig();
  return (
    <div style={{position: 'absolute', left: (e.zona?.izquierda ?? 40) + 20, right: (e.zona?.derecha ?? 140) + 20,
      top: e.y_pct * height, transform: 'translateY(-50%)', display: 'flex', justifyContent: 'center'}}>
      <div style={{background: e.fondo, borderRadius: 18, padding: '10px 28px', maxWidth: '100%',
        display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 18px'}}>
        {g.palabras.map((p, i) => {
          const activa = t >= p.inicio && t < p.fin;
          return (
            <span key={i} style={{fontFamily: e.fuente, fontSize: e.tam_px, fontWeight: 900, lineHeight: 1.15,
              color: activa || p.resalte ? e.color_activo : e.color,
              textTransform: e.mayusculas ? 'uppercase' : 'none'}}>
              {p.texto}
            </span>
          );
        })}
      </div>
    </div>
  );
};

export const Reel: React.FC<ReelProps> = ({video, subtitulos, ganchos, estilo}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const gancho = ganchos.find((g) => t >= g.inicio && t < g.fin);
  // Punch-in suave mientras dura un gancho (motion minimo, sin mover el audio).
  const escala = gancho
    ? interpolate(spring({frame: frame - Math.round(gancho.inicio * fps), fps, config: {damping: 200}}), [0, 1],
        [1, estilo.zoom_gancho])
    : 1;
  const grupo = subtitulos.find((g) => t >= g.inicio && t < g.fin);
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${escala})`}}>
        <OffthreadVideo src={staticFile(video)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      {gancho && gancho.texto ? (
        <div style={{position: 'absolute', left: '8%', right: '8%', top: '17%', textAlign: 'center',
          fontFamily: estilo.fuente, fontSize: Math.round(estilo.tam_px * 0.9), fontWeight: 900, color: estilo.color,
          textShadow: '0 4px 18px rgba(0,0,0,0.7)', textTransform: estilo.mayusculas ? 'uppercase' : 'none'}}>
          {gancho.texto}
        </div>
      ) : null}
      {grupo ? <Subtitulo g={grupo} e={estilo} t={t} /> : null}
    </AbsoluteFill>
  );
};
