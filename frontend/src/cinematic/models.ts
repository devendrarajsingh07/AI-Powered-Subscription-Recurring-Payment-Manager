import * as T from "three";

type Finish = {
  metal: T.MeshPhysicalMaterial;
  dark: T.MeshPhysicalMaterial;
  copper: T.MeshPhysicalMaterial;
  glass: T.MeshPhysicalMaterial;
};

function shapePlate(
  points: [number, number][],
  depth: number,
  bevel: number,
  material: T.Material,
) {
  const shape = new T.Shape();
  points.forEach(([x, y], index) =>
    index ? shape.lineTo(x, y) : shape.moveTo(x, y),
  );
  shape.closePath();
  const geometry = new T.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelSize: bevel,
    bevelThickness: bevel,
    bevelSegments: 4,
    steps: 1,
  });
  geometry.translate(0, 0, -depth / 2);
  return new T.Mesh(geometry, material);
}

function rounded(width: number, height: number, radius: number) {
  const x = width / 2;
  const y = height / 2;
  return new T.Shape()
    .moveTo(-x + radius, -y)
    .lineTo(x - radius, -y)
    .quadraticCurveTo(x, -y, x, -y + radius)
    .lineTo(x, y - radius)
    .quadraticCurveTo(x, y, x - radius, y)
    .lineTo(-x + radius, y)
    .quadraticCurveTo(-x, y, -x, y - radius)
    .lineTo(-x, -y + radius)
    .quadraticCurveTo(-x, -y, -x + radius, -y);
}

function roundedPlate(
  w: number,
  h: number,
  r: number,
  d: number,
  bevel: number,
  material: T.Material,
) {
  const geometry = new T.ExtrudeGeometry(rounded(w, h, r), {
    depth: d,
    bevelEnabled: true,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 4,
    curveSegments: 12,
  });
  geometry.translate(0, 0, -d / 2);
  return new T.Mesh(geometry, material);
}

function add(group: T.Group, mesh: T.Mesh, x = 0, y = 0, z = 0) {
  mesh.position.set(x, y, z);
  group.add(mesh);
  return mesh;
}

function box(w: number, h: number, d: number, material: T.Material) {
  return new T.Mesh(new T.BoxGeometry(w, h, d), material);
}

function disc(
  radius: number,
  depth: number,
  material: T.Material,
  segments = 64,
) {
  const mesh = new T.Mesh(
    new T.CylinderGeometry(radius, radius, depth, segments),
    material,
  );
  mesh.rotation.x = Math.PI / 2;
  return mesh;
}

function trace(points: number[][], material: T.Material, radius = 0.012) {
  const vectors = points.map(([x, y, z]) => new T.Vector3(x, y, z));
  const path = new T.CurvePath<T.Vector3>();
  for (let i = 1; i < vectors.length; i++)
    path.add(new T.LineCurve3(vectors[i - 1], vectors[i]));
  return new T.Mesh(
    new T.TubeGeometry(
      path,
      Math.max(12, vectors.length * 2),
      radius,
      6,
      false,
    ),
    material,
  );
}

function wordmark(material: T.MeshPhysicalMaterial) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.font = "600 78px sans-serif";
  context.textBaseline = "middle";
  context.fillStyle = "#19191b";
  context.fillText("SubTrack", 7, 68);
  context.fillStyle = "#847e76";
  context.fillText("SubTrack", 7, 64);
  const map = new T.CanvasTexture(canvas);
  map.colorSpace = T.SRGBColorSpace;
  const face = material.clone();
  face.map = map;
  face.color.set(0xffffff);
  face.alphaTest = 0.16;
  face.metalness = 0.48;
  return new T.Mesh(new T.PlaneGeometry(1.23, 0.3075), face);
}

function card({ metal, dark, copper }: Finish) {
  const group = new T.Group();
  add(group, roundedPlate(3.12, 1.94, 0.15, 0.083, 0.04, metal));
  for (const z of [-0.078, 0.078])
    add(group, roundedPlate(3.035, 1.86, 0.13, 0.018, 0.008, dark), 0, 0, z);
  const logo = wordmark(metal);
  if (logo) add(group, logo, -0.74, 0.55, 0.098);
  add(
    group,
    roundedPlate(0.61, 0.47, 0.083, 0.024, 0.017, copper),
    -0.94,
    -0.115,
    0.105,
  );
  const chipTraces = [
    [
      [-0.28, 0.1],
      [-0.14, 0.1],
      [-0.14, 0.2],
    ],
    [
      [-0.28, -0.1],
      [-0.14, -0.1],
      [-0.14, -0.2],
    ],
    [
      [0.28, 0.1],
      [0.14, 0.1],
      [0.14, 0.2],
    ],
    [
      [0.28, -0.1],
      [0.14, -0.1],
      [0.14, -0.2],
    ],
    [
      [-0.15, 0.2],
      [-0.09, 0.075],
      [0.09, 0.075],
      [0.15, 0.2],
    ],
    [
      [-0.15, -0.2],
      [-0.09, -0.075],
      [0.09, -0.075],
      [0.15, -0.2],
    ],
  ];
  chipTraces.forEach((points) =>
    add(
      group,
      trace(
        points.map(([x, y]) => [x - 0.94, y - 0.115, 0.136]),
        dark,
        0.008,
      ),
    ),
  );
  for (let i = 0; i < 4; i++) {
    const y = -0.79 + i * 0.16;
    const x = -0.93 + i * 0.22;
    add(
      group,
      trace(
        [
          [x, y, 0.097],
          [x + 0.53, y, 0.097],
          [x + 0.97, y + 0.26, 0.097],
          [1.42, y + 0.26, 0.097],
        ],
        i === 2 ? copper : metal,
        0.007,
      ),
    );
    add(group, disc(0.024, 0.009, copper, 16), x, y, 0.1);
  }
  add(group, box(2.88, 0.28, 0.012, dark), 0, 0.46, -0.105);
  return group;
}

function shield({ metal, dark, copper }: Finish) {
  const outer: [number, number][] = [
    [0, 1.48],
    [1.15, 1.01],
    [1.08, 0.03],
    [0.84, -0.6],
    [0.45, -1.08],
    [0, -1.41],
    [-0.45, -1.08],
    [-0.84, -0.6],
    [-1.08, 0.03],
    [-1.15, 1.01],
  ];
  const inset = (scale: number) =>
    outer.map(([x, y]): [number, number] => [x * scale, y * scale]);
  const group = new T.Group();
  add(group, shapePlate(outer, 0.22, 0.075, metal));
  add(group, shapePlate(inset(0.91), 0.075, 0.032, copper), 0, 0, 0.148);
  add(group, shapePlate(inset(0.85), 0.075, 0.045, dark), 0, 0, 0.204);
  add(
    group,
    trace(
      [
        [-0.46, 0.08, 0.31],
        [-0.13, -0.28, 0.31],
        [0.56, 0.44, 0.31],
      ],
      copper,
      0.065,
    ),
  );
  for (const [x, y] of [
    [-0.82, 0.78],
    [0.82, 0.78],
    [-0.68, -0.47],
    [0.68, -0.47],
  ])
    add(group, disc(0.036, 0.024, metal), x, y, 0.285);
  return group;
}

function capsule({ metal, dark, copper, glass }: Finish) {
  const group = new T.Group();
  const shell = new T.Mesh(new T.CapsuleGeometry(0.6, 1.92, 10, 48), glass);
  shell.rotation.z = Math.PI / 2;
  add(group, shell);
  add(group, roundedPlate(2.63, 0.74, 0.3, 0.28, 0.045, dark), 0, 0, 0.17);
  for (const x of [-0.97, 0.97]) {
    const band = new T.Mesh(new T.TorusGeometry(0.6, 0.039, 12, 72), metal);
    band.rotation.y = Math.PI / 2;
    add(group, band, x);
  }
  for (const x of [-0.76, 0.76]) {
    const band = new T.Mesh(new T.TorusGeometry(0.602, 0.026, 12, 72), copper);
    band.rotation.y = Math.PI / 2;
    add(group, band, x);
  }
  add(
    group,
    trace(
      [
        [-0.48, 0, 0.38],
        [0.44, 0, 0.38],
        [0.25, 0.17, 0.38],
      ],
      copper,
      0.029,
    ),
  );
  add(
    group,
    trace(
      [
        [0.44, 0, 0.38],
        [0.25, -0.17, 0.38],
      ],
      copper,
      0.029,
    ),
  );
  return group;
}

function ledger({ metal, dark, copper }: Finish) {
  const group = new T.Group();
  for (let layer = 0; layer < 4; layer++) {
    add(
      group,
      roundedPlate(2.66, 1.78, 0.15, 0.075, 0.035, layer === 3 ? dark : metal),
      (layer - 1.5) * -0.13,
      (layer - 1.5) * -0.14,
      (layer - 1.5) * 0.18,
    );
  }
  for (let row = 0; row < 3; row++) {
    const y = 0.16 - row * 0.35;
    add(group, disc(0.045, 0.025, copper), -0.93, y, 0.361);
    add(group, box(1.23, 0.028, 0.017, metal), -0.12, y, 0.361);
    add(group, box(0.27, 0.032, 0.019, copper), 0.75, y, 0.361);
  }
  add(group, box(1.87, 0.024, 0.017, copper), -0.16, 0.5, 0.36);
  return group;
}

function phone({ metal, dark, copper, glass }: Finish) {
  const group = new T.Group();
  add(group, roundedPlate(1.42, 2.84, 0.23, 0.13, 0.055, metal));
  add(group, roundedPlate(1.35, 2.76, 0.21, 0.03, 0.016, glass), 0, 0, 0.117);
  add(group, roundedPlate(1.35, 2.76, 0.21, 0.025, 0.016, dark), 0, 0, -0.111);
  add(
    group,
    roundedPlate(0.28, 0.068, 0.03, 0.016, 0.008, dark),
    0,
    1.24,
    0.154,
  );
  add(group, disc(0.029, 0.019, glass, 24), 0.076, 1.24, 0.166);
  for (const [x, y] of [
    [-0.758, 0.5],
    [-0.758, 0.15],
    [0.758, 0.34],
  ]) {
    add(
      group,
      roundedPlate(0.043, 0.24, 0.02, 0.07, 0.012, metal),
      x,
      y,
      0.024,
    );
  }
  add(
    group,
    roundedPlate(0.46, 0.49, 0.1, 0.032, 0.019, metal),
    -0.35,
    1.01,
    -0.161,
  );
  for (const [x, y] of [
    [-0.43, 1.1],
    [-0.29, 0.94],
  ]) {
    add(group, disc(0.083, 0.037, dark), x, y, -0.2);
    add(group, disc(0.054, 0.025, glass), x, y, -0.223);
  }
  const centerY = -0.22;
  for (const radius of [0.22, 0.36, 0.5]) {
    const points = Array.from({ length: 21 }, (_, i) => {
      const angle = -0.88 + (i * 1.76) / 20;
      return [
        radius * Math.sin(angle),
        centerY + radius * Math.cos(angle),
        0.165,
      ];
    });
    add(group, trace(points, copper, 0.02));
  }
  add(group, disc(0.035, 0.019, copper, 32), 0, centerY, 0.167);
  return group;
}

function vault({ metal, dark, copper }: Finish) {
  const group = new T.Group();
  add(group, roundedPlate(2.37, 2.38, 0.18, 0.61, 0.085, dark));
  add(group, disc(1.088, 0.13, metal), 0, 0, 0.384);
  add(group, disc(0.982, 0.145, dark), 0, 0, 0.474);
  add(group, disc(0.46, 0.13, metal), 0, 0, 0.579);
  add(group, disc(0.365, 0.14, dark), 0, 0, 0.645);
  add(group, disc(0.194, 0.14, copper), 0, 0, 0.717);
  for (let index = 0; index < 60; index++) {
    const angle = (index * Math.PI) / 30;
    const tick = add(
      group,
      box(0.012, index % 5 ? 0.035 : 0.06, 0.015, copper),
      Math.sin(angle) * 0.31,
      Math.cos(angle) * 0.31,
      0.727,
    );
    tick.rotation.z = -angle;
  }
  for (let index = 0; index < 8; index++) {
    const angle = (index * Math.PI) / 4;
    add(
      group,
      disc(0.049, 0.027, copper, 8),
      0.913 * Math.sin(angle),
      0.913 * Math.cos(angle),
      0.558,
    );
    if (index % 2 === 0) {
      const spoke = add(
        group,
        box(0.082, 0.39, 0.078, metal),
        0.66 * Math.sin(angle),
        0.66 * Math.cos(angle),
        0.584,
      );
      spoke.rotation.z = -angle;
    }
  }
  for (const y of [-0.66, 0.66]) {
    add(
      group,
      roundedPlate(0.34, 0.31, 0.058, 0.11, 0.03, metal),
      -1.0,
      y,
      0.42,
    );
    add(
      group,
      new T.Mesh(new T.CylinderGeometry(0.088, 0.088, 0.46, 28), copper),
      -1.15,
      y,
      0.504,
    );
  }
  add(
    group,
    trace(
      [
        [0.73, -0.35, 0.59],
        [0.73, -0.39, 0.73],
        [0.73, 0.39, 0.73],
        [0.73, 0.35, 0.59],
      ],
      copper,
      0.055,
    ),
  );
  return group;
}

export function createModels(visibility: { value: number }) {
  const bytes = new Uint8Array(128 * 128 * 4);
  let seed = 1151;
  for (let y = 0; y < 128; y++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const grain = 121 + (seed >>> 26);
    for (let x = 0; x < 128; x++) {
      const offset = (y * 128 + x) * 4;
      bytes.set([grain, grain, grain, 255], offset);
    }
  }
  const texture = new T.DataTexture(bytes, 128, 128);
  texture.wrapS = texture.wrapT = T.RepeatWrapping;
  texture.magFilter = T.LinearFilter;
  texture.minFilter = T.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.repeat.set(2, 2);
  texture.needsUpdate = true;
  const finish = {
    metal: new T.MeshPhysicalMaterial({
      color: 0x657380,
      metalness: 0.92,
      roughness: 0.34,
      anisotropy: 0.72,
      bumpMap: texture,
      bumpScale: 0.014,
    }),
    dark: new T.MeshPhysicalMaterial({
      color: 0x20262e,
      metalness: 0.84,
      roughness: 0.36,
      anisotropy: 0.8,
      clearcoat: 0.22,
      bumpMap: texture,
      bumpScale: 0.012,
    }),
    copper: new T.MeshPhysicalMaterial({
      color: 0xdca47b,
      metalness: 0.68,
      roughness: 0.33,
      emissive: 0x442315,
      emissiveIntensity: 0.19,
    }),
    glass: new T.MeshPhysicalMaterial({
      color: 0x232d38,
      metalness: 0.54,
      roughness: 0.15,
      clearcoat: 1,
      clearcoatRoughness: 0.12,
    }),
  };
  const models = [
    card(finish),
    shield(finish),
    capsule(finish),
    ledger(finish),
    phone(finish),
    vault(finish),
  ];
  const materials = new Set<T.MeshPhysicalMaterial>();
  models.forEach((model) =>
    model.traverse((node) => {
      if (node instanceof T.Mesh)
        materials.add(node.material as T.MeshPhysicalMaterial);
    }),
  );
  materials.forEach((material) => {
    material.onBeforeCompile = (shader) => {
      shader.uniforms.materialVisibility = visibility;
      shader.vertexShader =
        "varying vec3 vMaterialPosition;\n" +
        shader.vertexShader.replace(
          "#include <begin_vertex>",
          "#include <begin_vertex>\nvMaterialPosition = position;",
        );
      shader.fragmentShader =
        "varying vec3 vMaterialPosition;\nuniform float materialVisibility;\n" +
        shader.fragmentShader.replace(
          "#include <alphatest_fragment>",
          "#include <alphatest_fragment>\nvec3 grainCell = floor(vMaterialPosition * 115.0);\nfloat dissolve = fract(sin(dot(grainCell, vec3(12.9898, 78.233, 39.425))) * 43758.5453);\nif (dissolve > materialVisibility) discard;",
        );
    };
  });
  return models;
}
