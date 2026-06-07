import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { ORGANOS, rutasOrgano } from "./data.js";

const LAYOUT = {
  cerebro: { position: [0, 2.42, 0], scale: 0.9 },
  nasofaringe: { position: [0, 1.95, 0.02], scale: 0.42 },
  tiroides: { position: [0, 1.58, 0.06], scale: 0.42 },
  timo: { position: [0, 1.25, 0.04], scale: 0.44 },
  pulmones: { position: [0, 1.08, -0.02], scale: 1.02 },
  corazon: { position: [0.06, 1.04, 0.22], scale: 0.54 },
  higado: { position: [-0.34, 0.38, 0.12], scale: 0.92 },
  estomago: { position: [0.42, 0.38, 0.16], scale: 0.66 },
  pancreas: { position: [0.12, 0.46, 0.18], scale: 0.62 },
  rinones: { position: [0, 0.42, -0.08], scale: 0.72 },
  intestinos: { position: [0, -0.04, 0.16], scale: 0.96 },
  vejiga: { position: [0, -0.6, 0.18], scale: 0.56 },
  femenino: { position: [0, -0.8, 0.1], scale: 0.64 },
};

const ORDER = [
  "cerebro",
  "nasofaringe",
  "tiroides",
  "timo",
  "pulmones",
  "corazon",
  "higado",
  "estomago",
  "pancreas",
  "rinones",
  "intestinos",
  "vejiga",
  "femenino",
];

const SCENE_BG = new THREE.Color(0xf8f5f1);
const SPAWN = new THREE.Vector3(-1.92, 1.32, 0.18);
const DROP_THRESHOLD = 0.72;
const BODY_TEXTURE_PATH = (window.ASSETS_BASE || "../app-assets/") + "identidad/cuerpo_modelo.png";
const BODY_HEIGHT = 5.8;
const BODY_CENTER_Y = -0.15;
const BODY_Z = -0.5;

const state = {
  activeId: ORDER[0],
  placed: new Set(),
  placementOrder: [],
  hints: true,
  zoom: 7.4,
  showGrid: true,
  showShadows: false,
  showLabels: false,
  bodyOpacity: 1,
  autoAssembling: false,
};

const pieces = new Map();
const markers = new Map();
const $ = (selector) => document.querySelector(selector);
const els = {
  canvas: $("#assembly-canvas"),
  pieceGrid: $("#piece-grid"),
  pieceCounter: $("#piece-counter"),
  lessonTitle: $("#lesson-title"),
  lessonSummary: $("#lesson-summary"),
  lessonFunction: $("#lesson-function"),
  lessonLocation: $("#lesson-location"),
  lessonFact: $("#lesson-fact"),
  completionBanner: $("#completion-banner"),
  toast: $("#studio-toast"),
  toggleShadows: $("#toggle-shadows"),
  toggleGrid: $("#toggle-grid"),
  toggleLabels: $("#toggle-labels"),
};

const bodyMeshes = [];

const organosById = new Map(ORGANOS.map((organo) => [organo.id, organo]));
const loader = new GLTFLoader();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
const dragPoint = new THREE.Vector3();
const clock = new THREE.Clock();

const renderer = new THREE.WebGLRenderer({
  canvas: els.canvas,
  antialias: true,
  alpha: true,
  preserveDrawingBuffer: true,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(SCENE_BG, 1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = SCENE_BG;
scene.fog = new THREE.Fog(SCENE_BG, 7.6, 11.5);

const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
camera.position.set(4.7, 2.7, state.zoom);

const ZOOM_MIN = 2.5;
const ZOOM_MAX = 18;

const controls = new OrbitControls(camera, els.canvas);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = ZOOM_MIN;
controls.maxDistance = ZOOM_MAX;
controls.target.set(0, 0.18, 0);

const ambient = new THREE.HemisphereLight(0xffffff, 0xded5cb, 2.3);
scene.add(ambient);

const keyLight = new THREE.DirectionalLight(0xffffff, 3.4);
keyLight.position.set(4, 6, 5);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0xbfd8ff, 1.8);
fillLight.position.set(-4, 3, 4);
scene.add(fillLight);

const stageGroup = new THREE.Group();
scene.add(stageGroup);

const pieceLayer = new THREE.Group();
scene.add(pieceLayer);

const burstLayer = new THREE.Group();
scene.add(burstLayer);

const grid = new THREE.GridHelper(6.8, 22, 0xd8d6d1, 0xe7e2db);
grid.position.y = -1.66;
grid.rotation.x = Math.PI / 2;
stageGroup.add(grid);

const plinth = new THREE.Mesh(
  new THREE.BoxGeometry(4.5, 0.12, 2.2),
  new THREE.MeshStandardMaterial({
    color: 0xf4f0ea,
    roughness: 0.78,
    metalness: 0.02,
  })
);
plinth.position.set(0, -1.69, 0);
plinth.castShadow = false;
plinth.receiveShadow = true;
stageGroup.add(plinth);

createBodyScaffold();
createTargetMarkers();

const dragState = {
  piece: null,
  offset: new THREE.Vector3(),
  lastClient: { x: 0, y: 0 },
};

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("is-show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    els.toast.classList.remove("is-show");
  }, 1800);
}

function createBodyScaffold() {
  const textureLoader = new THREE.TextureLoader();
  textureLoader.load(
    BODY_TEXTURE_PATH,
    (texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

      const aspect =
        texture.image && texture.image.width
          ? texture.image.width / texture.image.height
          : 0.74;
      const width = BODY_HEIGHT * aspect;

      const material = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: state.bodyOpacity,
        depthWrite: false,
        side: THREE.DoubleSide,
        toneMapped: false,
      });

      const plane = new THREE.Mesh(
        new THREE.PlaneGeometry(width, BODY_HEIGHT),
        material
      );
      plane.position.set(0, BODY_CENTER_Y, BODY_Z);
      plane.userData.isBody = true;
      plane.renderOrder = -1;
      bodyMeshes.push(plane);
      stageGroup.add(plane);
    },
    undefined,
    (error) => {
      console.error(
        `No se pudo cargar la imagen del cuerpo en ${BODY_TEXTURE_PATH}`,
        error
      );
    }
  );
}

function normalizeModel(root, scaleFactor) {
  const clone = root.clone(true);
  const box = new THREE.Box3().setFromObject(clone);
  const size = box.getSize(new THREE.Vector3());
  const maxDimension = Math.max(size.x, size.y, size.z) || 1;
  const scalar = scaleFactor / maxDimension;
  clone.scale.setScalar(scalar);

  const centeredBox = new THREE.Box3().setFromObject(clone);
  const center = centeredBox.getCenter(new THREE.Vector3());
  clone.position.sub(center);

  clone.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = true;
    node.receiveShadow = true;
  });

  return clone;
}

function cloneAsGhost(object) {
  const ghost = object.clone(true);
  ghost.traverse((node) => {
    if (!node.isMesh) return;
    node.material = new THREE.MeshStandardMaterial({
      color: 0x8bb7ff,
      transparent: true,
      opacity: 0.2,
      roughness: 0.4,
      emissive: 0x1957b7,
      emissiveIntensity: 0.1,
    });
  });
  return ghost;
}

function createTargetMarkers() {
  ORDER.forEach((id) => {
    const marker = new THREE.Group();
    marker.position.fromArray(LAYOUT[id].position);

    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(0.22, 0.014, 12, 48),
      new THREE.MeshBasicMaterial({
        color: 0x7aa8f4,
        transparent: true,
        opacity: 0.42,
      })
    );
    halo.rotation.x = Math.PI / 2;

    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.05, 18, 18),
      new THREE.MeshBasicMaterial({
        color: 0x2368d9,
        transparent: true,
        opacity: 0.28,
      })
    );

    marker.add(halo, core);
    marker.userData.halo = halo;
    marker.userData.core = core;
    stageGroup.add(marker);
    markers.set(id, marker);
  });
}

function updateMarkerStates() {
  markers.forEach((marker, id) => {
    const isPlaced = state.placed.has(id);
    const isActive = id === state.activeId;
    marker.visible = state.hints && state.showLabels && !isPlaced;
    marker.scale.setScalar(isActive ? 1.3 : 1);
    marker.userData.halo.material.opacity = isActive ? 0.95 : 0.32;
    marker.userData.core.material.opacity = isActive ? 0.65 : 0.18;
  });
}

function ensurePieceLoaded(id) {
  const existing = pieces.get(id);
  if (existing) return Promise.resolve(existing);

  const organo = organosById.get(id);
  const config = LAYOUT[id];

  return new Promise((resolve, reject) => {
    loader.load(
      rutasOrgano(organo).modelo,
      (gltf) => {
        const normalized = normalizeModel(gltf.scene, config.scale);

        const live = new THREE.Group();
        live.add(normalized.clone(true));
        live.position.copy(SPAWN);
        live.visible = false;
        live.userData.id = id;

        const ghost = new THREE.Group();
        ghost.add(cloneAsGhost(normalized));
        ghost.position.fromArray(config.position);
        ghost.visible = false;

        pieceLayer.add(ghost, live);
        const piece = {
          id,
          live,
          ghost,
          target: new THREE.Vector3(...config.position),
          placed: false,
        };
        pieces.set(id, piece);
        resolve(piece);
      },
      undefined,
      reject
    );
  });
}

function renderPieceGrid() {
  els.pieceGrid.innerHTML = ORDER.map((id) => {
    const organo = organosById.get(id);
    const rutas = rutasOrgano(organo);
    const active = id === state.activeId ? "is-active" : "";
    const placed = state.placed.has(id) ? "is-placed" : "";
    return `
      <button class="piece-card ${active} ${placed}" data-id="${id}" draggable="false">
        <img src="${rutas.imagen}" alt="${organo.nombre}" draggable="false" />
        <strong>${organo.nombre}</strong>
        <small>${state.placed.has(id) ? "Colocado" : "Pendiente"}</small>
      </button>
    `;
  }).join("");

  els.pieceGrid.querySelectorAll(".piece-card").forEach((button) => {
    attachCardInteraction(button, button.dataset.id);
  });
}

function attachCardInteraction(button, id) {
  let pointerStart = null;
  let dragTransferred = false;
  let pendingSelect = null;

  const onMove = (event) => {
    if (!pointerStart || dragTransferred) return;
    const dx = event.clientX - pointerStart.x;
    const dy = event.clientY - pointerStart.y;
    if (Math.hypot(dx, dy) < 6) return;
    dragTransferred = true;
    if (!pendingSelect) return;
    pendingSelect.then(() => {
      const piece = pieces.get(id);
      if (!piece || piece.placed) return;
      setPointer(event);
      raycaster.setFromCamera(pointer, camera);
      raycaster.ray.intersectPlane(dragPlane, dragPoint);
      piece.live.position.copy(dragPoint);
      piece.live.visible = true;
      dragState.piece = piece;
      dragState.lastClient = { x: event.clientX, y: event.clientY };
      dragState.offset.set(0, 0, 0);
      controls.enabled = false;
    });
  };

  const cleanup = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", cleanup);
    pointerStart = null;
  };

  button.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    if (state.autoAssembling) return;
    event.preventDefault();
    pointerStart = { x: event.clientX, y: event.clientY };
    dragTransferred = false;
    pendingSelect = selectPiece(id);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", cleanup);
  });
}

function updateEducationalPanels(id) {
  const organo = organosById.get(id);
  els.lessonTitle.textContent = organo.nombre;
  els.lessonSummary.textContent = organo.resumen;
  els.lessonFunction.textContent = organo.funcion;
  els.lessonLocation.textContent = organo.ubicacion;
  els.lessonFact.textContent = organo.datoCurioso;
}

function updateProgress() {
  const count = state.placed.size;
  const total = ORDER.length;
  if (els.pieceCounter) {
    els.pieceCounter.textContent = `${count} / ${total} colocadas`;
  }

  if (count === total) {
    els.completionBanner.classList.add("is-visible");
  } else {
    els.completionBanner.classList.remove("is-visible");
  }

  // Actualizar el pill de progreso de HALU (barra de contexto superior)
  const pill = document.getElementById("halu-piezas-label");
  if (pill) pill.textContent = `${count}/13 piezas`;

  // Reportar progreso al servidor HALU
  if (window.API_PROGRESO_URL && window.CSRF_TOKEN) {
    fetch(window.API_PROGRESO_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.CSRF_TOKEN,
      },
      body: JSON.stringify({ piezas_colocadas: count }),
    }).catch(() => {}); // Falla silenciosamente
  }
}

let selectToken = 0;

async function selectPiece(id) {
  if (state.placed.has(id)) {
    updateEducationalPanels(id);
    renderPieceGrid();
    toast(`${organosById.get(id).nombre} ya está colocado`);
    return;
  }

  state.activeId = id;
  const currentToken = ++selectToken;
  updateEducationalPanels(id);
  renderPieceGrid();
  updateMarkerStates();

  let active;
  try {
    active = await ensurePieceLoaded(id);
  } catch (error) {
    toast(`No se pudo cargar ${organosById.get(id).nombre}`);
    console.error(error);
    return;
  }

  if (currentToken !== selectToken) return;
  pieces.forEach((piece) => {
    if (piece.placed) return;
    piece.live.visible = piece.id === id;
    piece.ghost.visible = state.hints && piece.id === id;
    piece.ghost.traverse((node) => {
      if (node.isMesh && node.material) {
        node.material.opacity = 0.34;
        node.material.emissiveIntensity = 0.34;
      }
    });
  });

  active.live.position.copy(SPAWN);
  active.ghost.visible = state.hints;
}

function nextPendingId() {
  const pending = ORDER.filter((id) => !state.placed.has(id));
  if (!pending.length) return null;
  return pending[Math.floor(Math.random() * pending.length)];
}

async function selectNextPending() {
  const nextId = nextPendingId();
  if (!nextId) return;
  await selectPiece(nextId);
}

function placePiece(piece) {
  piece.placed = true;
  piece.live.position.copy(piece.target);
  piece.live.visible = true;
  piece.ghost.visible = false;
  state.placed.add(piece.id);
  state.placementOrder.push(piece.id);
  state.activeId = null;
  updateMarkerStates();
  updateEducationalPanels(piece.id);
  updateProgress();
  renderPieceGrid();
  toast(`${organosById.get(piece.id).nombre} colocado`);
  pulsePiece(piece.live);

  if (state.placed.size === ORDER.length) {
    celebrate();
  }
}

function updateBodyOpacity() {
  bodyMeshes.forEach((mesh) => {
    if (mesh.material) {
      mesh.material.opacity = state.bodyOpacity;
      mesh.material.transparent = true;
      mesh.material.needsUpdate = true;
    }
  });
}

function setShadows(enabled) {
  state.showShadows = enabled;
  renderer.shadowMap.enabled = enabled;
  keyLight.castShadow = enabled;
  scene.traverse((obj) => {
    if (obj.isMesh && obj.material) {
      obj.material.needsUpdate = true;
    }
  });
}

function setGridVisible(visible) {
  state.showGrid = visible;
  grid.visible = visible;
}

function setLabelsVisible(visible) {
  state.showLabels = visible;
  updateMarkerStates();
}

function pulsePiece(group) {
  group.userData.pulse = 1;
}

function undoLastPlacement() {
  const lastId = state.placementOrder.pop();
  if (!lastId) {
    toast("No hay piezas para deshacer");
    return;
  }

  const piece = pieces.get(lastId);
  piece.placed = false;
  piece.live.position.copy(SPAWN);
  piece.live.visible = true;
  piece.ghost.visible = state.hints;
  state.placed.delete(lastId);
  state.activeId = lastId;
  updateProgress();
  updateMarkerStates();
  selectPiece(lastId);
}

function resetAssembly() {
  state.placed.clear();
  state.placementOrder = [];
  pieces.forEach((piece) => {
    piece.placed = false;
    piece.live.visible = false;
    piece.live.position.copy(SPAWN);
    piece.ghost.visible = false;
  });
  state.activeId = ORDER[0];
  updateProgress();
  updateMarkerStates();
  selectPiece(state.activeId);
  toast("Armado reiniciado");
}

function celebrate() {
  burstLayer.clear();
  const geometry = new THREE.BufferGeometry();
  const points = [];
  const colors = [];
  const palette = [0x2368d9, 0x1f9d72, 0xf5a524, 0xd84f70];

  for (let i = 0; i < 120; i += 1) {
    points.push(
      (Math.random() - 0.5) * 2.6,
      0.8 + Math.random() * 2.1,
      (Math.random() - 0.5) * 1.2
    );
    const color = new THREE.Color(palette[i % palette.length]);
    colors.push(color.r, color.g, color.b);
  }

  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.08,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
  });
  const burst = new THREE.Points(geometry, material);
  burst.userData.createdAt = performance.now();
  burstLayer.add(burst);
}

function setHints(enabled) {
  state.hints = enabled;
  $("#btn-hints").classList.toggle("is-active", enabled);
  pieces.forEach((piece) => {
    piece.ghost.visible = enabled && !piece.placed && piece.id === state.activeId;
  });
  updateMarkerStates();
}

function resizeRenderer() {
  const { clientWidth, clientHeight } = els.canvas;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
}

function setPointer(event) {
  const rect = els.canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function onPointerDown(event) {
  if (!state.activeId) return;
  const piece = pieces.get(state.activeId);
  if (!piece || piece.placed || !piece.live.visible) return;

  setPointer(event);
  raycaster.setFromCamera(pointer, camera);
  const activeMarker = markers.get(state.activeId);
  const markerHits = activeMarker
    ? raycaster.intersectObject(activeMarker, true)
    : [];
  if (markerHits.length) {
    placePiece(piece);
    return;
  }

  const hits = raycaster.intersectObject(piece.live, true);
  if (!hits.length) return;

  raycaster.ray.intersectPlane(dragPlane, dragPoint);
  dragState.piece = piece;
  dragState.lastClient = { x: event.clientX, y: event.clientY };
  dragState.offset.copy(piece.live.position).sub(dragPoint);
  controls.enabled = false;
}

function onPointerMove(event) {
  if (!dragState.piece) return;
  setPointer(event);
  dragState.lastClient = { x: event.clientX, y: event.clientY };
  raycaster.setFromCamera(pointer, camera);
  raycaster.ray.intersectPlane(dragPlane, dragPoint);
  dragState.piece.live.position.copy(dragPoint).add(dragState.offset);
  dragState.piece.live.position.x = THREE.MathUtils.clamp(
    dragState.piece.live.position.x,
    -2.25,
    2.25
  );
  dragState.piece.live.position.y = THREE.MathUtils.clamp(
    dragState.piece.live.position.y,
    -1.45,
    2.8
  );
}

function onPointerUp(event) {
  if (!dragState.piece) return;
  const piece = dragState.piece;
  const distance = piece.live.position.distanceTo(piece.target);
  const screenTarget = piece.target.clone().project(camera);
  const targetX = (screenTarget.x * 0.5 + 0.5) * els.canvas.clientWidth;
  const targetY = (-screenTarget.y * 0.5 + 0.5) * els.canvas.clientHeight;
  const rect = els.canvas.getBoundingClientRect();
  const clientX = event?.clientX ?? dragState.lastClient.x;
  const clientY = event?.clientY ?? dragState.lastClient.y;
  const screenDistance = Math.hypot(
    clientX - rect.left - targetX,
    clientY - rect.top - targetY
  );

  if (distance <= DROP_THRESHOLD || screenDistance <= 90) {
    placePiece(piece);
  } else {
    piece.live.position.copy(SPAWN);
    toast("Acércala más a la silueta");
  }
  dragState.piece = null;
  controls.enabled = true;
}

function onCanvasClick(event) {
  const piece = pieces.get(state.activeId);
  if (!piece || piece.placed) return;
  setPointer(event);
  raycaster.setFromCamera(pointer, camera);
  const activeMarker = markers.get(state.activeId);
  if (!activeMarker) return;
  const markerHits = raycaster.intersectObject(activeMarker, true);
  if (markerHits.length) placePiece(piece);
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  controls.update();

  pieces.forEach((piece) => {
    if (piece.live.userData.pulse) {
      piece.live.userData.pulse = Math.max(0, piece.live.userData.pulse - delta * 1.8);
      const scale = 1 + piece.live.userData.pulse * 0.08;
      piece.live.scale.setScalar(scale);
      if (!piece.live.userData.pulse) piece.live.scale.setScalar(1);
    }
  });

  burstLayer.children.forEach((burst) => {
    const age = performance.now() - burst.userData.createdAt;
    burst.position.y += delta * 0.35;
    burst.material.opacity = Math.max(0, 1 - age / 1800);
    if (age > 1800) burstLayer.remove(burst);
  });

  renderer.render(scene, camera);
}

function bindEvents() {
  els.canvas.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("pointermove", onPointerMove);
  els.canvas.addEventListener("click", onCanvasClick);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("resize", resizeRenderer);

  $("#btn-place").addEventListener("click", () => {
    autoAssemble();
  });
  $("#btn-focus").addEventListener("click", () => {
    camera.position.set(4.7, 2.7, state.zoom);
    controls.target.set(0, 0.18, 0);
    controls.update();
  });

  $("#btn-hints").addEventListener("click", () => setHints(!state.hints));
  $("#btn-zoom-in").addEventListener("click", () => {
    state.zoom = Math.max(ZOOM_MIN, state.zoom - 0.6);
    camera.position.setLength(state.zoom);
  });
  $("#btn-zoom-out").addEventListener("click", () => {
    state.zoom = Math.min(ZOOM_MAX, state.zoom + 0.6);
    camera.position.setLength(state.zoom);
  });
  $("#btn-undo").addEventListener("click", undoLastPlacement);
  $("#btn-reset").addEventListener("click", resetAssembly);
  $("#btn-shuffle").addEventListener("click", () => {
    const pending = ORDER.filter((id) => !state.placed.has(id));
    if (!pending.length) {
      toast("Todas las piezas están colocadas");
      return;
    }
    selectPiece(pending[Math.floor(Math.random() * pending.length)]);
  });

  if (els.toggleShadows) {
    els.toggleShadows.addEventListener("change", (event) => {
      setShadows(event.target.checked);
    });
  }
  if (els.toggleGrid) {
    els.toggleGrid.addEventListener("change", (event) => {
      setGridVisible(event.target.checked);
    });
  }
  if (els.toggleLabels) {
    els.toggleLabels.addEventListener("change", (event) => {
      setLabelsVisible(event.target.checked);
    });
  }
}

function preloadPieces() {
  ORDER.forEach((id) => {
    ensurePieceLoaded(id).catch((error) => {
      console.warn(`No se pudo precargar ${id}`, error);
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function animatePieceToTarget(piece, duration = 650) {
  return new Promise((resolve) => {
    const start = piece.live.position.clone();
    const end = piece.target.clone();
    const startTime = performance.now();
    const step = () => {
      const elapsed = performance.now() - startTime;
      const t = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      piece.live.position.lerpVectors(start, end, eased);
      if (t < 1) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
}

async function autoAssemble() {
  if (state.autoAssembling) return;
  if (state.placed.size === ORDER.length) {
    toast("El cuerpo ya está armado");
    return;
  }
  state.autoAssembling = true;
  const placeBtn = $("#btn-place");
  if (placeBtn) placeBtn.classList.add("is-running");
  toast("Armando el cuerpo…");

  try {
    const pending = ORDER.filter((id) => !state.placed.has(id));
    for (const id of pending) {
      if (!state.autoAssembling) break;
      await selectPiece(id);
      const piece = pieces.get(id);
      if (!piece || piece.placed) continue;
      await animatePieceToTarget(piece);
      placePiece(piece);
      await sleep(450);
    }
  } finally {
    state.autoAssembling = false;
    if (placeBtn) placeBtn.classList.remove("is-running");
  }
}

async function init() {
  renderPieceGrid();
  updateEducationalPanels(state.activeId);
  updateProgress();
  updateMarkerStates();
  refreshIcons();
  resizeRenderer();
  bindEvents();
  animate();

  setShadows(state.showShadows);
  setGridVisible(state.showGrid);
  setLabelsVisible(state.showLabels);
  updateBodyOpacity();

  try {
    globalThis.__assemblyDebug = {
      renderer,
      scene,
      camera,
      pieces,
      markers,
      placeById: async (id) => {
        await selectPiece(id);
        const piece = pieces.get(id);
        if (piece && !piece.placed) placePiece(piece);
      },
    };
    await selectPiece(state.activeId);
  } catch (error) {
    toast("No se pudieron cargar las piezas");
    console.error(error);
  }

  preloadPieces();
}

init();
