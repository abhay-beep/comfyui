// Camera-lens finish for Dev's three.js scenes, using pmndrs/postprocessing (zlib licence).
//
// importmap (postprocessing 6.35.x is the line that supports three r160):
//   "postprocessing": "https://cdn.jsdelivr.net/npm/postprocessing@6.35.5/build/index.js"
//
// In scene.js, replace `renderer.render(scene, camera)` with `post.render(t)`:
//   import { createPost } from './post.js';
//   const post = createPost(renderer, scene, camera, {
//     dof: { focus: (t) => ({ distance: camera.position.distanceTo(dev.position), range: 0.3, bokeh: 8 }) },
//     bloom: { intensity: 0.6 },
//   });
//
// Every setting is a number or a function of t (seconds), so focus can follow a beat.
// Rendering only depends on t, which keeps HyperFrames' frame-by-frame render deterministic.
import * as THREE from 'three';
import {
  EffectComposer, RenderPass, EffectPass, DepthOfFieldEffect, BloomEffect, VignetteEffect,
  ChromaticAberrationEffect, ToneMappingEffect, ToneMappingMode,
} from 'postprocessing';

const at = (v, t) => (typeof v === 'function' ? v(t) : v);

// render targets skip the renderer's tone mapping, so the composer has to redo it
const TONE = {
  [THREE.LinearToneMapping]: ToneMappingMode.LINEAR,
  [THREE.ReinhardToneMapping]: ToneMappingMode.REINHARD,
  [THREE.CineonToneMapping]: ToneMappingMode.OPTIMIZED_CINEON,
  [THREE.ACESFilmicToneMapping]: ToneMappingMode.ACES_FILMIC,
  ...(THREE.AgXToneMapping !== undefined && { [THREE.AgXToneMapping]: ToneMappingMode.AGX }),
};

export function createPost(renderer, scene, camera, opts = {}) {
  const { dof, bloom, vignette = {}, chroma, fps = 30 } = opts;
  if (dof && renderer.capabilities.logarithmicDepthBuffer) {
    console.warn('post.js: depth of field reads the depth buffer and is wrong with logarithmicDepthBuffer');
  }

  const composer = new EffectComposer(renderer, {
    frameBufferType: THREE.HalfFloatType,                     // keeps highlights above 1.0 for bloom
    multisampling: renderer.capabilities.isWebGL2 ? 4 : 0,    // the canvas's antialias doesn't reach render targets
  });
  composer.addPass(new RenderPass(scene, camera));

  const effects = {};
  if (dof) {
    effects.dof = new DepthOfFieldEffect(camera, { focusDistance: 0, focusRange: 0.1, bokehScale: 6, resolutionScale: 0.75 });
    composer.addPass(new EffectPass(camera, effects.dof));    // blur effects each need their own pass
  }

  const finish = [];
  if (bloom) {
    effects.bloom = new BloomEffect({
      mipmapBlur: true,
      intensity: at(bloom.intensity ?? 0.6, 0),
      luminanceThreshold: bloom.threshold ?? 0.85,
      luminanceSmoothing: 0.2,
      radius: bloom.radius ?? 0.7,
    });
    finish.push(effects.bloom);
  }
  if (renderer.toneMapping !== THREE.NoToneMapping && TONE[renderer.toneMapping] !== undefined) {
    finish.push(new ToneMappingEffect({ mode: TONE[renderer.toneMapping] }));
  }
  if (vignette) {
    effects.vignette = new VignetteEffect({ offset: at(vignette.offset ?? 0.35, 0), darkness: at(vignette.darkness ?? 0.45, 0) });
    finish.push(effects.vignette);
  }
  if (finish.length) composer.addPass(new EffectPass(camera, ...finish));

  if (chroma) {
    effects.chroma = new ChromaticAberrationEffect({ radialModulation: true, modulationOffset: 0.2 });
    composer.addPass(new EffectPass(camera, effects.chroma));
  }

  const size = renderer.getSize(new THREE.Vector2());
  composer.setSize(size.x, size.y, false);

  function render(t) {
    if (effects.dof) {
      const f = at(dof.focus, t) ?? {};
      const coc = effects.dof.cocMaterial;
      coc.copyCameraSettings(camera);                         // near/far may move between beats
      if (f.target) {
        effects.dof.target = f.target.getWorldPosition(effects.dof.target ?? new THREE.Vector3());
      } else {
        effects.dof.target = null;
        coc.worldFocusDistance = f.distance ?? 1;
      }
      coc.worldFocusRange = f.range ?? 0.5;
      effects.dof.bokehScale = f.bokeh ?? 6;   // ~6-10 reads at 1080x1920; 2 is barely visible
    }
    if (effects.bloom) effects.bloom.intensity = at(bloom.intensity ?? 0.6, t);
    if (effects.vignette) {
      effects.vignette.offset = at(vignette.offset ?? 0.35, t);
      effects.vignette.darkness = at(vignette.darkness ?? 0.45, t);
    }
    if (effects.chroma) {
      const a = at(chroma.amount ?? 0.0015, t);
      effects.chroma.offset.set(a, a * 0.5);
    }
    composer.render(1 / fps);                                  // fixed step: no wall-clock timing
  }

  return {
    composer, effects, render,
    setSize: (w, h) => composer.setSize(w, h, false),
    dispose: () => composer.dispose(),
  };
}
