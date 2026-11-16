import * as T from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { MeshSurfaceSampler } from "three/addons/math/MeshSurfaceSampler.js";
import { createModels } from "./models";

export type Pose = { x: number; y: number; dragging: boolean };
const POINT_COUNT = 4800;
const TAU = Math.PI * 2;

function randomGenerator() {
  let seed = 29213;
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

function sample(model: T.Group, random: () => number) {
  const positions = new Float32Array(POINT_COUNT * 3);
  const samplers: { end: number; mesh: T.Mesh; sampler: MeshSurfaceSampler }[] =
    [];
  let total = 0;
  model.updateMatrixWorld(true);
  model.traverse((node) => {
    if (!(node instanceof T.Mesh)) return;
    node.geometry.computeBoundingBox();
    const size = node.geometry.boundingBox?.getSize(new T.Vector3());
    if (!size) return;
    total += Math.max(
      0.001,
      size.x * size.y + size.x * size.z + size.y * size.z,
    );
    samplers.push({
      end: total,
      mesh: node,
      sampler: new MeshSurfaceSampler(node).build(),
    });
  });
  const vertex = new T.Vector3();
  for (let i = 0; i < POINT_COUNT; i++) {
    const weight = random() * total;
    const entry =
      samplers.find(({ end }) => end > weight) ?? samplers[samplers.length - 1];
    entry.sampler.sample(vertex);
    vertex.applyMatrix4(entry.mesh.matrixWorld).toArray(positions, i * 3);
  }
  return positions;
}

function cubic(x: number) {
  const clamped = T.MathUtils.clamp(x, 0, 1);
  return clamped * clamped * (3 - 2 * clamped);
}

function particleMaterial() {
  return new T.ShaderMaterial({
    uniforms: { opacity: { value: 0 }, pixelRatio: { value: 1 } },
    vertexShader: `
      attribute float seed;
      varying float vSeed;
      uniform float pixelRatio;
      void main() {
        vSeed = seed;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        gl_PointSize = (1.8 + seed * 3.0) * pixelRatio * (5.0 / -mvPosition.z);
      }
    `,
    fragmentShader: `
      uniform float opacity;
      varying float vSeed;
      void main() {
        float r = length(gl_PointCoord - vec2(0.5));
        float core = 1.0 - smoothstep(0.0, 0.5, r);
        vec3 cool = vec3(0.52, 0.71, 0.88);
        vec3 copper = vec3(1.0, 0.59, 0.32);
        gl_FragColor = vec4(mix(cool, copper, smoothstep(0.18, 0.72, vSeed)), core * opacity * (0.30 + vSeed * 0.63));
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: T.AdditiveBlending,
  });
}

function orbit(radius: number, thickness: number, warm: boolean) {
  const track = new T.Group();
  const ring = new T.Mesh(
    new T.TorusGeometry(radius, thickness, 10, 160),
    new T.MeshPhysicalMaterial({
      color: warm ? 0xd08b5c : 0x65717e,
      metalness: warm ? 0.46 : 0.8,
      roughness: 0.29,
      emissive: warm ? 0xdd783a : 0x3a4a5c,
      emissiveIntensity: warm ? 0.58 : 0.19,
    }),
  );
  track.add(ring);
  const markerMaterial = new T.MeshStandardMaterial({
    color: 0xeac7a5,
    emissive: warm ? 0xf7a467 : 0x7aaacd,
    emissiveIntensity: warm ? 0.86 : 0.58,
  });
  const markerGeometry = new T.SphereGeometry(warm ? 0.033 : 0.024, 10, 8);
  const markers = [
    new T.Mesh(markerGeometry, markerMaterial),
    new T.Mesh(markerGeometry, markerMaterial),
  ];
  track.add(...markers);
  return { track, markers, radius };
}

function disposeScene(scene: T.Object3D) {
  const disposed = new Set<T.Material | T.Texture | T.BufferGeometry>();
  const dispose = (resource: T.Material | T.Texture | T.BufferGeometry) => {
    if (!disposed.has(resource)) {
      disposed.add(resource);
      resource.dispose();
    }
  };
  scene.traverse((item) => {
    if (item instanceof T.Mesh || item instanceof T.Points) {
      dispose(item.geometry);
      const materials: T.Material[] = Array.isArray(item.material)
        ? item.material
        : [item.material];
      for (const material of materials) {
        Object.values(material).forEach((value) => {
          if (value instanceof T.Texture) dispose(value);
        });
        dispose(material);
      }
    }
  });
}

export function mountScene(
  canvas: HTMLCanvasElement,
  getProgress: () => number,
  getPose: () => Pose,
  ready: () => void,
  fail: () => void,
) {
  const renderer = new T.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
  });
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(39, 1, 0.1, 45);
  const pmrem = new T.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, 0.055, 0.1, 100);
  room.dispose();
  pmrem.dispose();
  scene.environment = environment.texture;
  scene.environmentIntensity = 0.83;
  renderer.setClearColor(0x10141a, 0);
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  const cool = new T.DirectionalLight(0xacccef, 3.2);
  cool.position.set(2.5, 3, 3);
  const warm = new T.DirectionalLight(0xed9a6c, 1.5);
  warm.position.set(-2.8, -0.9, 2.1);
  const back = new T.DirectionalLight(0x9eaccb, 2.9);
  back.position.set(1.2, -1.9, -3);
  scene.add(cool, warm, back, new T.HemisphereLight(0xc9d9ef, 0x3b2722, 1.09));

  const visibility = { value: 1 };
  const models = createModels(visibility);
  const random = randomGenerator();
  const clouds = models.map((model) => sample(model, random));
  const object = new T.Group();
  scene.add(object);
  object.add(...models);
  const particles = new T.BufferGeometry();
  const positions = new Float32Array(POINT_COUNT * 3);
  const seed = new Float32Array(POINT_COUNT);
  const orb = new Float32Array(POINT_COUNT * 3);
  for (let i = 0; i < POINT_COUNT; i++) {
    seed[i] = random();
    const vertical = random() * 2 - 1;
    const phi = random() * TAU;
    const radius = 0.37 + random() * 0.32;
    const horizontal = Math.sqrt(1 - vertical * vertical);
    orb.set(
      [
        radius * horizontal * Math.cos(phi),
        radius * vertical,
        radius * horizontal * Math.sin(phi),
      ],
      i * 3,
    );
  }
  const positionAttribute = new T.BufferAttribute(positions, 3).setUsage(
    T.DynamicDrawUsage,
  );
  particles.setAttribute("position", positionAttribute);
  particles.setAttribute("seed", new T.BufferAttribute(seed, 1));
  const dustMaterial = particleMaterial();
  const dust = new T.Points(particles, dustMaterial);
  dust.frustumCulled = false;
  object.add(dust);

  const tracks = [
    orbit(2.06, 0.017, true),
    orbit(2.29, 0.008, false),
    orbit(1.84, 0.007, false),
  ];
  scene.add(...tracks.map(({ track }) => track));
  const aim = new T.Vector3();
  let lastTime = performance.now();
  let runningTime = 0;
  let frame = 0;
  let mounted = true;
  let reportedReady = false;
  let stopped = false;

  function resize() {
    if (stopped) return;
    const { width, height } = canvas.getBoundingClientRect();
    if (!width || !height) return;
    const pixelRatio = Math.min(window.devicePixelRatio, 1.65);
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.position.set(0, 0.12, Math.max(7.15, 7.55 / camera.aspect));
    camera.lookAt(aim);
    camera.updateProjectionMatrix();
    dustMaterial.uniforms.pixelRatio.value = pixelRatio;
  }

  function draw(now: number) {
    if (!mounted || stopped) return;
    const delta = Math.min((now - lastTime) / 1000, 0.038);
    lastTime = now;
    runningTime += delta;
    const time = runningTime;
    const progress = T.MathUtils.clamp(getProgress(), 0, models.length - 1);
    const from = Math.floor(progress);
    const next = Math.min(from + 1, models.length - 1);
    const fraction = progress - from;
    const shift = cubic((fraction - 0.55) / 0.4);
    warm.intensity = 1.4 + (from + shift) * 0.28;
    cool.intensity = 3.2 - (from + shift) * 0.21;
    const selected = fraction >= 0.55 ? next : from;
    const gone = cubic((fraction - 0.15) / 0.31);
    visibility.value = fraction < 0.55 ? 1 - gone : shift;
    models.forEach((model, index) => {
      model.visible = index === selected && visibility.value > 0.012;
    });
    dust.visible = fraction > 0.15 && fraction < 0.97;
    if (dust.visible) {
      const a = fraction < 0.5 ? clouds[from] : clouds[next];
      const blend =
        fraction < 0.5
          ? cubic((fraction - 0.15) / 0.35)
          : 1 - cubic((fraction - 0.5) / 0.47);
      const billow = Math.sin(blend * Math.PI) * 0.29;
      const spin = blend * 1.9;
      const sin = Math.sin(spin);
      const cos = Math.cos(spin);
      for (let i = 0; i < positions.length; i += 3) {
        const offset = seed[i / 3] * TAU * 3;
        const x = orb[i] * cos - orb[i + 2] * sin;
        const z = orb[i] * sin + orb[i + 2] * cos;
        positions[i] =
          T.MathUtils.lerp(a[i], x, blend) + Math.cos(offset) * billow;
        positions[i + 1] =
          T.MathUtils.lerp(a[i + 1], orb[i + 1], blend) +
          Math.sin(offset) * billow;
        positions[i + 2] =
          T.MathUtils.lerp(a[i + 2], z, blend) +
          Math.cos(offset * 1.7) * billow;
      }
      positionAttribute.needsUpdate = true;
      dustMaterial.uniforms.opacity.value = Math.min(1, blend * 2.3);
    }
    const pose = getPose();
    const ease = 1 - Math.exp(-delta * (pose.dragging ? 14 : 7));
    object.rotation.x +=
      (0.12 + pose.x + Math.sin(time * 0.45) * 0.025 - object.rotation.x) *
      ease;
    object.rotation.y +=
      (-0.28 + pose.y + Math.sin(time * 0.38) * 0.16 - object.rotation.y) *
      ease;
    object.rotation.z = 0.11 + Math.sin(time * 0.51) * 0.021;
    object.position.y = Math.sin(time * 0.71) * 0.07;
    tracks.forEach(({ track, markers, radius }, index) => {
      track.rotation.set(
        1.19 - index * 0.63,
        0.32 + index * 0.39,
        time * (0.12 + index * 0.045) + index * 0.73,
      );
      markers.forEach((marker, markerIndex) => {
        const phase =
          time * (0.61 - index * 0.12) + markerIndex * 2.73 + index * 2;
        marker.position.set(
          Math.cos(phase) * radius,
          Math.sin(phase) * radius,
          0,
        );
      });
    });
    try {
      renderer.render(scene, camera);
    } catch {
      stopped = true;
      fail();
      return;
    }
    if (!reportedReady) {
      reportedReady = true;
      ready();
    }
    frame = requestAnimationFrame(draw);
  }
  function lost(event: Event) {
    event.preventDefault();
    stopped = true;
    cancelAnimationFrame(frame);
    fail();
  }
  const sizeObserver = new ResizeObserver(resize);
  const viewportObserver = new IntersectionObserver(([entry]) => {
    cancelAnimationFrame(frame);
    if (entry.isIntersecting && !stopped) {
      lastTime = performance.now();
      frame = requestAnimationFrame(draw);
    }
  });
  resize();
  sizeObserver.observe(canvas);
  viewportObserver.observe(canvas);
  canvas.addEventListener("webglcontextlost", lost);
  return () => {
    mounted = false;
    cancelAnimationFrame(frame);
    sizeObserver.disconnect();
    viewportObserver.disconnect();
    canvas.removeEventListener("webglcontextlost", lost);
    disposeScene(scene);
    environment.dispose();
    renderer.dispose();
    if (!renderer.getContext().isContextLost()) renderer.forceContextLoss();
  };
}
