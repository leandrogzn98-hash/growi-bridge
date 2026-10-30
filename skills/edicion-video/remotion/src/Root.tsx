import React from 'react';
import {Composition} from 'remotion';
import {Reel, ReelProps, propsPorDefecto} from './Reel';

// Duracion, tamaño y fps salen de los props (los escribe editar.py en props.json).
export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    defaultProps={propsPorDefecto}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={30}
    calculateMetadata={({props}: {props: ReelProps}) => ({
      durationInFrames: Math.max(1, Math.round(props.duracion_s * (props.fps || 30))),
      fps: props.fps || 30,
      width: props.ancho || 1080,
      height: props.alto || 1920,
    })}
  />
);
