/**
 * Remarobe Solar 3D Equipment Visualiser (High Performance & Self-Contained)
 * =========================================================================
 * Interactive Three.js scene showing recommended solar equipment
 * with exact quantities, branded specifications, and 3D models.
 *
 * Performance & Reliability Optimizations:
 *   - 100% self-contained local dependencies (no CDN blocking, no importmap errors)
 *   - Strict try/catch/finally error boundary with safety timeout
 *   - Auto-frames directly on equipment bounding box (not the ground plane)
 *   - On-demand dynamic import of GLTFLoader
 *   - Geometry & Material pooling (prototype sharing) for O(1) procedural generation
 *   - Resolution-scaled shadow maps (1024x1024 desktop, 512x512 mobile)
 *   - Visibility-based render pausing to ensure 0% idle CPU/GPU usage
 */

import * as THREE from '../three/three.module.js';
import { OrbitControls } from '../three/OrbitControls.js';

/* ================================================================
   THEME & COLOUR PALETTE
   ================================================================ */

const COLORS = {
    background: 0xf8fafc,
    ground:     0xedf2f7,
    gridMain:   0xcbd5e1,
    gridSub:    0xe2e8f0,
    panel:      0x1e3a8a,      // deep photovoltaic blue
    panelFrame: 0x94a3b8,      // anodized aluminum
    panelGrid:  0x93c5fd,      // busbar lines
    battery:    0x1e293b,      // dark battery chassis
    batteryTop: 0x16a34a,      // Remarobe green accent
    inverter:   0xf1f5f9,      // clean white-gray housing
    inverterFace: 0x15803d,    // inverter accent panel
    controller: 0xe2e8f0,      // controller housing
    controllerFace: 0x2563eb,  // controller LCD
    ambient:    0xffffff,
    directional: 0xffffff,
    hemisphere: { sky: 0xdbeafe, ground: 0x334155 },
};

const DIMENSIONS = {
    // Physical dimensions in metres (1 unit = 1 metre)
    panel:      { w: 1.134, h: 0.035, d: 2.278 },   // 550W-650W tier
    battery:    { w: 0.480, h: 0.650, d: 0.220 },   // wall/floor LiFePO4
    inverter:   { w: 0.420, h: 0.620, d: 0.210 },   // 5kVA-12kVA hybrid
    controller: { w: 0.240, h: 0.440, d: 0.120 },   // MPPT charge controller
};

const SPACING = {
    panelGapX: 0.10,
    panelGapZ: 0.15,
    batteryGap: 0.10,
    inverterGap: 0.18,
    controllerGap: 0.12,
    groupGap: 2.40,
};

/* ================================================================
   DYNAMIC GLTF MODEL LOADER & CACHE
   ================================================================ */

let _gltfLoader = null;
const modelCache = new Map();

async function getGLTFLoader() {
    if (!_gltfLoader) {
        const { GLTFLoader } = await import('../three/GLTFLoader.js');
        _gltfLoader = new GLTFLoader();
    }
    return _gltfLoader;
}

async function loadGLBModel(url) {
    if (!url) return null;
    if (modelCache.has(url)) {
        return modelCache.get(url).clone(true);
    }
    try {
        const loader = await getGLTFLoader();
        return await new Promise((resolve) => {
            loader.load(
                url,
                (gltf) => {
                    const model = gltf.scene || gltf.scenes[0];
                    model.traverse((child) => {
                        if (child.isMesh) {
                            child.castShadow = true;
                            child.receiveShadow = true;
                        }
                    });
                    modelCache.set(url, model);
                    resolve(model.clone(true));
                },
                undefined,
                (err) => {
                    console.warn(`[Solar3D] Could not load GLB from ${url}. Using procedural model.`, err);
                    resolve(null);
                }
            );
        });
    } catch (e) {
        console.warn(`[Solar3D] GLTFLoader load failed:`, e);
        return null;
    }
}

function safeFloat(v, fallback = 0) {
    const n = parseFloat(v);
    return isFinite(n) ? n : fallback;
}

/* ================================================================
   FLOATING LABELS
   ================================================================ */

function createLabelTexture(lines, opts = {}) {
    const fontSize = opts.fontSize || 42;
    const padding = opts.padding || 20;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    ctx.font = `900 ${fontSize}px "Montserrat", Arial, sans-serif`;
    const maxWidth = Math.max(...lines.map(l => ctx.measureText(l).width));
    canvas.width = Math.ceil(maxWidth + padding * 2);
    canvas.height = Math.ceil((fontSize * 1.35) * lines.length + padding * 2);

    // Pill background
    ctx.fillStyle = opts.bg || '#fff7d6';
    ctx.beginPath();
    ctx.roundRect(0, 0, canvas.width, canvas.height, 14);
    ctx.fill();

    // Border
    ctx.strokeStyle = opts.border || '#92400e';
    ctx.lineWidth = 4;
    ctx.stroke();

    // Text rendering
    ctx.textBaseline = 'top';
    lines.forEach((line, i) => {
        ctx.font = i === 0 ? `900 ${fontSize}px "Montserrat", Arial, sans-serif` : `700 ${fontSize * 0.85}px "Montserrat", Arial, sans-serif`;
        ctx.fillStyle = i === 0 ? (opts.titleColor || '#0f172a') : '#1e293b';
        ctx.fillText(line, padding, padding + i * fontSize * 1.35);
    });

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return { texture, aspect: canvas.width / canvas.height };
}

function createLabelSprite(lines, position, scale = 1.0) {
    const { texture, aspect } = createLabelTexture(lines);
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
    });
    const sprite = new THREE.Sprite(material);
    const h = 0.88 * scale;
    sprite.scale.set(h * aspect, h, 1);
    sprite.position.copy(position);
    return sprite;
}

/* ================================================================
   POOLED GEOMETRIES & MATERIALS FOR FAST MESH INSTANTIATION
   ================================================================ */

let _sharedGeos = null;
let _sharedMats = null;

function getSharedResources() {
    if (_sharedGeos && _sharedMats) return { geos: _sharedGeos, mats: _sharedMats };

    const pDim = DIMENSIONS.panel;
    const bDim = DIMENSIONS.battery;
    const iDim = DIMENSIONS.inverter;
    const cDim = DIMENSIONS.controller;
    const frameThick = 0.016;

    _sharedGeos = {
        // Solar Panel
        panelBody: new THREE.BoxGeometry(pDim.w, pDim.h, pDim.d),
        panelFrameSide: new THREE.BoxGeometry(frameThick, pDim.h + 0.006, pDim.d + frameThick),
        panelFrameEnd: new THREE.BoxGeometry(pDim.w, pDim.h + 0.006, frameThick),
        panelLineZ: new THREE.BoxGeometry(0.003, 0.001, pDim.d * 0.94),
        panelLineX: new THREE.BoxGeometry(pDim.w * 0.94, 0.001, 0.003),

        // Battery
        batteryBody: new THREE.BoxGeometry(bDim.w, bDim.h, bDim.d),
        batteryTop: new THREE.BoxGeometry(bDim.w * 0.98, bDim.h * 0.07, bDim.d * 0.98),
        batteryLed: new THREE.CylinderGeometry(0.007, 0.007, 0.004, 8),
        batteryTerminal: new THREE.CylinderGeometry(0.018, 0.018, 0.025, 12),

        // Inverter
        inverterBody: new THREE.BoxGeometry(iDim.w, iDim.h, iDim.d),
        inverterDisplay: new THREE.BoxGeometry(iDim.w * 0.65, iDim.h * 0.26, 0.005),
        inverterLed: new THREE.SphereGeometry(0.007, 8, 8),

        // Controller
        controllerBody: new THREE.BoxGeometry(cDim.w, cDim.h, cDim.d),
        controllerDisplay: new THREE.BoxGeometry(cDim.w * 0.65, cDim.h * 0.22, 0.004),
    };

    _sharedMats = {
        // Solar Panel
        panel: new THREE.MeshStandardMaterial({
            color: COLORS.panel,
            metalness: 0.55,
            roughness: 0.22,
        }),
        panelFrame: new THREE.MeshStandardMaterial({
            color: COLORS.panelFrame,
            metalness: 0.85,
            roughness: 0.2,
        }),
        panelGrid: new THREE.MeshBasicMaterial({
            color: COLORS.panelGrid,
            transparent: true,
            opacity: 0.20,
        }),

        // Battery
        battery: new THREE.MeshStandardMaterial({
            color: COLORS.battery,
            metalness: 0.35,
            roughness: 0.55,
        }),
        batteryTop: new THREE.MeshStandardMaterial({
            color: COLORS.batteryTop,
            metalness: 0.2,
            roughness: 0.4,
        }),
        ledGreen: new THREE.MeshStandardMaterial({
            color: 0x16a34a,
            emissive: 0x16a34a,
            emissiveIntensity: 0.6,
        }),
        ledBlue: new THREE.MeshStandardMaterial({
            color: 0x3b82f6,
            emissive: 0x3b82f6,
            emissiveIntensity: 0.6,
        }),
        ledYellow: new THREE.MeshStandardMaterial({
            color: 0xeab308,
            emissive: 0xeab308,
            emissiveIntensity: 0.5,
        }),
        terminalRed: new THREE.MeshStandardMaterial({
            color: 0xdc2626,
            metalness: 0.8,
            roughness: 0.25,
        }),
        terminalBlack: new THREE.MeshStandardMaterial({
            color: 0x2563eb,
            metalness: 0.8,
            roughness: 0.25,
        }),

        // Inverter
        inverter: new THREE.MeshStandardMaterial({
            color: COLORS.inverter,
            metalness: 0.2,
            roughness: 0.6,
        }),
        inverterFace: new THREE.MeshStandardMaterial({
            color: COLORS.inverterFace,
            metalness: 0.3,
            roughness: 0.35,
            emissive: COLORS.inverterFace,
            emissiveIntensity: 0.2,
        }),

        // Controller
        controller: new THREE.MeshStandardMaterial({
            color: COLORS.controller,
            metalness: 0.15,
            roughness: 0.65,
        }),
        controllerFace: new THREE.MeshStandardMaterial({
            color: COLORS.controllerFace,
            metalness: 0.2,
            roughness: 0.4,
            emissive: COLORS.controllerFace,
            emissiveIntensity: 0.2,
        }),
    };

    return { geos: _sharedGeos, mats: _sharedMats };
}

/* ================================================================
   PROCEDURAL EQUIPMENT PROTOTYPES (Instant Cloning)
   ================================================================ */

let _panelPrototype = null;
function buildSolarPanel() {
    if (_panelPrototype) return _panelPrototype.clone(true);

    const { geos, mats } = getSharedResources();
    const group = new THREE.Group();
    const dim = DIMENSIONS.panel;

    // PV Dark Blue Glass
    const panel = new THREE.Mesh(geos.panelBody, mats.panel);
    panel.position.y = dim.h / 2;
    panel.castShadow = true;
    panel.receiveShadow = true;
    group.add(panel);

    // Frame side bars
    [-1, 1].forEach(side => {
        const f = new THREE.Mesh(geos.panelFrameSide, mats.panelFrame);
        f.position.set(side * (dim.w / 2), dim.h / 2, 0);
        group.add(f);
    });

    [-1, 1].forEach(side => {
        const f = new THREE.Mesh(geos.panelFrameEnd, mats.panelFrame);
        f.position.set(0, dim.h / 2, side * (dim.d / 2));
        group.add(f);
    });

    // Busbars
    const cellCols = 6;
    const cellRows = 12;
    for (let i = 1; i < cellCols; i++) {
        const line = new THREE.Mesh(geos.panelLineZ, mats.panelGrid);
        line.position.set(-dim.w * 0.47 + i * (dim.w * 0.94 / cellCols), dim.h + 0.001, 0);
        group.add(line);
    }
    for (let j = 1; j < cellRows; j++) {
        const line = new THREE.Mesh(geos.panelLineX, mats.panelGrid);
        line.position.set(0, dim.h + 0.001, -dim.d * 0.47 + j * (dim.d * 0.94 / cellRows));
        group.add(line);
    }

    // Solar tilt angle (~15 degrees southward)
    group.rotation.x = -Math.PI * 15 / 180;
    group.userData.equipmentType = 'panel';

    _panelPrototype = group;
    return _panelPrototype.clone(true);
}

let _batteryPrototype = null;
function buildBattery() {
    if (_batteryPrototype) return _batteryPrototype.clone(true);

    const { geos, mats } = getSharedResources();
    const group = new THREE.Group();
    const dim = DIMENSIONS.battery;

    // Main dark battery enclosure
    const body = new THREE.Mesh(geos.batteryBody, mats.battery);
    body.position.y = dim.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    // Green branding top strip
    const topStrip = new THREE.Mesh(geos.batteryTop, mats.batteryTop);
    topStrip.position.y = dim.h * 0.96;
    group.add(topStrip);

    // Front status LEDs
    [mats.ledGreen, mats.ledGreen, mats.ledGreen, mats.ledBlue].forEach((ledMat, i) => {
        const led = new THREE.Mesh(geos.batteryLed, ledMat);
        led.rotation.x = Math.PI / 2;
        led.position.set(-dim.w * 0.25 + i * (dim.w * 0.16), dim.h * 0.84, dim.d / 2 + 0.002);
        group.add(led);
    });

    // Heavy DC terminals
    [-0.14, 0.14].forEach((xOff, idx) => {
        const term = new THREE.Mesh(geos.batteryTerminal, idx === 0 ? mats.terminalRed : mats.terminalBlack);
        term.position.set(xOff, dim.h + 0.012, 0);
        group.add(term);
    });

    group.userData.equipmentType = 'battery';
    _batteryPrototype = group;
    return _batteryPrototype.clone(true);
}

let _inverterPrototype = null;
function buildInverter() {
    if (_inverterPrototype) return _inverterPrototype.clone(true);

    const { geos, mats } = getSharedResources();
    const group = new THREE.Group();
    const dim = DIMENSIONS.inverter;

    // Main housing
    const body = new THREE.Mesh(geos.inverterBody, mats.inverter);
    body.position.y = dim.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    // Accent LCD / Status screen
    const display = new THREE.Mesh(geos.inverterDisplay, mats.inverterFace);
    display.position.set(0, dim.h * 0.64, dim.d / 2 + 0.003);
    group.add(display);

    // Status indicators
    [mats.ledGreen, mats.ledYellow, mats.ledBlue].forEach((ledMat, i) => {
        const led = new THREE.Mesh(geos.inverterLed, ledMat);
        led.position.set(-dim.w * 0.20 + i * (dim.w * 0.20), dim.h * 0.44, dim.d / 2 + 0.004);
        group.add(led);
    });

    group.userData.equipmentType = 'inverter';
    _inverterPrototype = group;
    return _inverterPrototype.clone(true);
}

let _controllerPrototype = null;
function buildController() {
    if (_controllerPrototype) return _controllerPrototype.clone(true);

    const { geos, mats } = getSharedResources();
    const group = new THREE.Group();
    const dim = DIMENSIONS.controller;

    const body = new THREE.Mesh(geos.controllerBody, mats.controller);
    body.position.y = dim.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const display = new THREE.Mesh(geos.controllerDisplay, mats.controllerFace);
    display.position.set(0, dim.h * 0.68, dim.d / 2 + 0.003);
    group.add(display);

    group.userData.equipmentType = 'controller';
    _controllerPrototype = group;
    return _controllerPrototype.clone(true);
}

/* ================================================================
   SCENE BUILDER & CONTROLLER
   ================================================================ */

class SolarVisualizer {
    constructor(containerId, dataId) {
        this.container = document.getElementById(containerId);
        this.dataEl = document.getElementById(dataId);
        if (!this.container) return;

        this.equipmentData = {};
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.animationId = null;
        this.disposed = false;
        this._isVisible = true;

        this.loadingEl = this.container.querySelector('.solar-3d-loading');

        this._parseData();
        this._checkWebGL();
    }

    _parseData() {
        if (!this.dataEl) {
            this.equipmentData = {};
            return;
        }
        try {
            const raw = this.dataEl.textContent ? this.dataEl.textContent.trim() : '{}';
            this.equipmentData = JSON.parse(raw || '{}');
        } catch (e) {
            console.warn('[Solar3D] Could not parse equipment data JSON:', e);
            this.equipmentData = {};
        }
    }

    _checkWebGL() {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
        if (!gl) {
            this._showFallback('WebGL is not supported by your browser or graphics hardware.');
            return;
        }

        // Safety watchdog: ensure spinner is never stuck spinning if something hangs
        const safetyTimer = setTimeout(() => {
            if (this.loadingEl && this.loadingEl.style.display !== 'none') {
                console.warn('[Solar3D] Watchdog safety timeout triggered — hiding spinner');
                this.loadingEl.style.display = 'none';
            }
        }, 3500);

        this.init()
            .catch(err => {
                console.error('[Solar3D] Scene initialization failed:', err);
                this._showFallback('Could not load 3D scene: ' + (err.message || 'Please reload page'));
            })
            .finally(() => {
                clearTimeout(safetyTimer);
                if (this.loadingEl) {
                    this.loadingEl.style.display = 'none';
                }
            });
    }

    _showFallback(message) {
        if (this.loadingEl) this.loadingEl.style.display = 'none';
        const fb = this.container.querySelector('.solar-3d-fallback');
        if (fb) {
            fb.style.display = 'flex';
            const msgEl = fb.querySelector('.solar-3d-fallback-msg');
            if (msgEl) msgEl.textContent = message;
        }
    }

    async init() {
        const width = this.container.clientWidth || 800;
        const height = Math.max(this.container.clientHeight || 460, 460);

        // Three.js Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(COLORS.background);
        this.scene.fog = new THREE.Fog(COLORS.background, 25, 75);

        // Perspective Camera
        this.camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
        this.camera.position.set(7, 6, 9);

        // WebGL Renderer
        const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
        this.renderer = new THREE.WebGLRenderer({
            antialias: !isMobile,
            powerPreference: 'high-performance',
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.08;

        const canvasWrapper = this.container.querySelector('.solar-3d-canvas-wrapper');
        if (canvasWrapper) {
            canvasWrapper.innerHTML = '';
            canvasWrapper.appendChild(this.renderer.domElement);
        } else {
            this.container.appendChild(this.renderer.domElement);
        }

        // OrbitControls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.minDistance = 2.5;
        this.controls.maxDistance = 35;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.04;
        this.controls.target.set(0, 0.8, 0);
        this.controls.update();

        // Lighting & Ground
        this._setupLighting();
        this._setupGround();

        // Build 3D Equipment
        await this._buildEquipment();

        // Frame camera to loaded bounds
        this._frameCameraToScene();

        // Setup resize, buttons, observer
        this._onResize = this._handleResize.bind(this);
        window.addEventListener('resize', this._onResize);
        this._setupControls();
        this._setupVisibilityObserver();

        // Render first frame immediately
        this.renderer.render(this.scene, this.camera);

        // Start render loop
        this._animate();
    }

    _setupLighting() {
        const hemi = new THREE.HemisphereLight(
            COLORS.hemisphere.sky,
            COLORS.hemisphere.ground,
            0.55
        );
        this.scene.add(hemi);

        const ambient = new THREE.AmbientLight(COLORS.ambient, 0.35);
        this.scene.add(ambient);

        const sun = new THREE.DirectionalLight(COLORS.directional, 1.25);
        sun.position.set(9, 14, 7);
        sun.castShadow = true;

        const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
        const shadowSize = isMobile ? 512 : 1024;
        sun.shadow.mapSize.width = shadowSize;
        sun.shadow.mapSize.height = shadowSize;
        sun.shadow.camera.near = 0.5;
        sun.shadow.camera.far = 50;
        sun.shadow.camera.left = -16;
        sun.shadow.camera.right = 16;
        sun.shadow.camera.top = 16;
        sun.shadow.camera.bottom = -16;
        sun.shadow.bias = -0.0008;
        this.scene.add(sun);

        const fill = new THREE.DirectionalLight(0xe0f2fe, 0.30);
        fill.position.set(-6, 7, -5);
        this.scene.add(fill);
    }

    _setupGround() {
        const groundGeo = new THREE.PlaneGeometry(44, 44);
        const groundMat = new THREE.MeshStandardMaterial({
            color: COLORS.ground,
            metalness: 0.05,
            roughness: 0.85,
        });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        this.scene.add(ground);

        const grid = new THREE.GridHelper(44, 44, COLORS.gridMain, COLORS.gridSub);
        grid.position.y = 0.004;
        grid.material.transparent = true;
        grid.material.opacity = 0.35;
        this.scene.add(grid);
    }

    async _buildEquipment() {
        const data = this.equipmentData;
        if (!data || !data.equipment) {
            this._showFallback('No recommended equipment data found.');
            return;
        }

        const equip = data.equipment;
        const groups = [];
        let currentZ = 0;

        // === 1. SOLAR PANELS ===
        const panelCount = safeFloat(equip.panels?.quantity, 0);
        if (panelCount > 0) {
            const panelGroup = new THREE.Group();
            panelGroup.name = 'panels';

            const glbUrl = equip.panels?.asset?.asset_url;
            let loadedMesh = null;
            if (glbUrl) {
                loadedMesh = await loadGLBModel(glbUrl);
            }

            const dim = DIMENSIONS.panel;
            const maxCols = Math.min(panelCount, 4);
            const rows = Math.ceil(panelCount / maxCols);
            const stepX = dim.w + SPACING.panelGapX;
            const stepZ = dim.d + SPACING.panelGapZ;

            let idx = 0;
            for (let r = 0; r < rows && idx < panelCount; r++) {
                const colsInRow = Math.min(maxCols, panelCount - idx);
                const rowStartX = -(colsInRow - 1) * stepX / 2;
                for (let c = 0; c < colsInRow && idx < panelCount; c++) {
                    const pMesh = loadedMesh ? loadedMesh.clone(true) : buildSolarPanel();
                    pMesh.position.set(
                        rowStartX + c * stepX,
                        0.75, // mount elevation
                        -(rows - 1) * stepZ / 2 + r * stepZ
                    );
                    panelGroup.add(pMesh);
                    idx++;
                }
            }

            // Label
            const pSpec = equip.panels;
            const pStatus = pSpec.asset?.has_exact_model ? '✓ Verified Model' : '○ Procedural 3D Model';
            const pLines = [
                `☀ ${panelCount} × Solar Panels`,
                `${pSpec.name || 'PV Module'} (${pSpec.rating || ''})`,
                pStatus,
            ];

            const pBox = new THREE.Box3().setFromObject(panelGroup);
            const pLabelPos = new THREE.Vector3(0, pBox.max.y + 1.0, 0);
            panelGroup.add(createLabelSprite(pLines, pLabelPos, 1.35));

            panelGroup.position.z = currentZ;
            this.scene.add(panelGroup);
            groups.push(panelGroup);

            const pSize = pBox.getSize(new THREE.Vector3());
            currentZ += pSize.z / 2 + SPACING.groupGap;
        }

        // === 2. BATTERIES ===
        const batteryCount = safeFloat(equip.batteries?.quantity, 0);
        if (batteryCount > 0) {
            const batteryGroup = new THREE.Group();
            batteryGroup.name = 'batteries';

            const bGlbUrl = equip.batteries?.asset?.asset_url;
            let loadedBMesh = null;
            if (bGlbUrl) {
                loadedBMesh = await loadGLBModel(bGlbUrl);
            }

            const dim = DIMENSIONS.battery;
            const maxCols = Math.min(batteryCount, 6);
            const rows = Math.ceil(batteryCount / maxCols);
            const step = dim.w + SPACING.batteryGap;

            let bIdx = 0;
            for (let r = 0; r < rows && bIdx < batteryCount; r++) {
                const colsInRow = Math.min(maxCols, batteryCount - bIdx);
                const rowStartX = -(colsInRow - 1) * step / 2;
                for (let c = 0; c < colsInRow && bIdx < batteryCount; c++) {
                    const bMesh = loadedBMesh ? loadedBMesh.clone(true) : buildBattery();
                    bMesh.position.set(
                        rowStartX + c * step,
                        0,
                        r * (dim.d + SPACING.batteryGap)
                    );
                    batteryGroup.add(bMesh);
                    bIdx++;
                }
            }

            const bBox = new THREE.Box3().setFromObject(batteryGroup);
            const bSize = bBox.getSize(new THREE.Vector3());
            batteryGroup.position.z = currentZ + bSize.z / 2;

            const bSpec = equip.batteries;
            const bStatus = bSpec.asset?.has_exact_model ? '✓ Verified Model' : '○ Procedural 3D Model';
            const bLines = [
                `🔋 ${batteryCount} × Battery Bank`,
                `${bSpec.name || 'LiFePO4 Storage'} (${bSpec.rating || ''})`,
                bStatus,
            ];
            const bLabelPos = new THREE.Vector3(0, bBox.max.y + 0.85, 0);
            batteryGroup.add(createLabelSprite(bLines, bLabelPos, 1.25));

            this.scene.add(batteryGroup);
            groups.push(batteryGroup);

            currentZ = batteryGroup.position.z + bSize.z / 2 + SPACING.groupGap;
        }

        // === 3. INVERTER ===
        const inverterCount = safeFloat(equip.inverter?.quantity, 0);
        if (inverterCount > 0) {
            const inverterGroup = new THREE.Group();
            inverterGroup.name = 'inverters';

            const iGlbUrl = equip.inverter?.asset?.asset_url;
            let loadedIMesh = null;
            if (iGlbUrl) {
                loadedIMesh = await loadGLBModel(iGlbUrl);
            }

            const dim = DIMENSIONS.inverter;
            const step = dim.w + SPACING.inverterGap;
            const startX = -(inverterCount - 1) * step / 2;

            for (let i = 0; i < inverterCount; i++) {
                const iMesh = loadedIMesh ? loadedIMesh.clone(true) : buildInverter();
                iMesh.position.set(startX + i * step, 0, 0);
                inverterGroup.add(iMesh);
            }

            const iBox = new THREE.Box3().setFromObject(inverterGroup);

            // Position to the right of batteries
            const batGroup = this.scene.getObjectByName('batteries');
            if (batGroup) {
                const bBounds = new THREE.Box3().setFromObject(batGroup);
                inverterGroup.position.x = bBounds.max.x + 1.25;
                inverterGroup.position.z = batGroup.position.z;
            } else {
                inverterGroup.position.z = currentZ + iBox.getSize(new THREE.Vector3()).z / 2;
            }

            const iSpec = equip.inverter;
            const iStatus = iSpec.asset?.has_exact_model ? '✓ Verified Model' : '○ Procedural 3D Model';
            const iLines = [
                `⚡ ${inverterCount} × Inverter`,
                `${iSpec.name || 'Hybrid Inverter'} (${iSpec.rating || ''})`,
                iStatus,
            ];
            const iLabelPos = new THREE.Vector3(0, iBox.max.y + 0.85, 0);
            inverterGroup.add(createLabelSprite(iLines, iLabelPos, 1.25));

            this.scene.add(inverterGroup);
            groups.push(inverterGroup);
        }

        // === 4. CHARGE CONTROLLER (if standalone) ===
        const controllerCount = safeFloat(equip.controller?.quantity, 0);
        if (controllerCount > 0) {
            const ctrlGroup = new THREE.Group();
            ctrlGroup.name = 'controllers';

            const cGlbUrl = equip.controller?.asset?.asset_url;
            let loadedCMesh = null;
            if (cGlbUrl) {
                loadedCMesh = await loadGLBModel(cGlbUrl);
            }

            const dim = DIMENSIONS.controller;
            const step = dim.w + SPACING.controllerGap;
            const startX = -(controllerCount - 1) * step / 2;

            for (let i = 0; i < controllerCount; i++) {
                const cMesh = loadedCMesh ? loadedCMesh.clone(true) : buildController();
                cMesh.position.set(startX + i * step, 0, 0);
                ctrlGroup.add(cMesh);
            }

            const cBox = new THREE.Box3().setFromObject(ctrlGroup);

            const batGroup = this.scene.getObjectByName('batteries');
            if (batGroup) {
                const bBounds = new THREE.Box3().setFromObject(batGroup);
                ctrlGroup.position.x = bBounds.min.x - 0.95;
                ctrlGroup.position.z = batGroup.position.z;
            } else {
                ctrlGroup.position.z = currentZ + cBox.getSize(new THREE.Vector3()).z / 2;
            }

            const cSpec = equip.controller;
            const cStatus = cSpec.asset?.has_exact_model ? '✓ Verified Model' : '○ Procedural 3D Model';
            const cLines = [
                `🔧 ${controllerCount} × Charge Controller`,
                `${cSpec.name || 'MPPT Controller'} (${cSpec.rating || ''})`,
                cStatus,
            ];
            const cLabelPos = new THREE.Vector3(0, cBox.max.y + 0.85, 0);
            ctrlGroup.add(createLabelSprite(cLines, cLabelPos, 1.25));

            this.scene.add(ctrlGroup);
            groups.push(ctrlGroup);
        }

        // Fallback if no equipment is available
        if (groups.length === 0) {
            this._showFallback('No solar equipment selected to visualize.');
            return;
        }

        // Centre whole equipment arrangement at origin (0, 0, 0)
        const sceneBox = new THREE.Box3();
        groups.forEach(g => sceneBox.expandByObject(g));
        const centre = sceneBox.getCenter(new THREE.Vector3());
        groups.forEach(g => {
            g.position.x -= centre.x;
            g.position.z -= centre.z;
        });
    }

    _frameCameraToScene() {
        const equipBox = new THREE.Box3();
        let hasEquip = false;
        ['panels', 'batteries', 'inverters', 'controllers'].forEach(name => {
            const grp = this.scene.getObjectByName(name);
            if (grp) {
                equipBox.expandByObject(grp);
                hasEquip = true;
            }
        });

        const box = hasEquip ? equipBox : new THREE.Box3().setFromObject(this.scene);
        const size = box.getSize(new THREE.Vector3());
        const centre = box.getCenter(new THREE.Vector3());

        const maxDim = Math.max(size.x, size.y, size.z, 2.0);
        const fov = this.camera.fov * (Math.PI / 180);
        let dist = maxDim / (2 * Math.tan(fov / 2));
        dist = Math.max(dist * 1.35, 5.0);

        this.camera.position.set(
            centre.x + dist * 0.65,
            centre.y + dist * 0.50,
            centre.z + dist * 0.70
        );
        this.controls.target.set(centre.x, Math.max(centre.y, 0.4), centre.z);
        this.controls.update();

        this._initialCameraPos = this.camera.position.clone();
        this._initialTarget = this.controls.target.clone();
    }

    _setupControls() {
        const resetBtn = this.container.querySelector('[data-solar3d-action="reset"]');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetView());
        }

        const fsBtn = this.container.querySelector('[data-solar3d-action="fullscreen"]');
        if (fsBtn) {
            fsBtn.addEventListener('click', () => this.toggleFullscreen());
        }

        const zoomIn = this.container.querySelector('[data-solar3d-action="zoom-in"]');
        const zoomOut = this.container.querySelector('[data-solar3d-action="zoom-out"]');
        if (zoomIn) {
            zoomIn.addEventListener('click', () => {
                this.camera.position.lerp(this.controls.target, 0.22);
                this.controls.update();
            });
        }
        if (zoomOut) {
            zoomOut.addEventListener('click', () => {
                const dir = new THREE.Vector3().subVectors(this.camera.position, this.controls.target).normalize();
                this.camera.position.addScaledVector(dir, 1.8);
                this.controls.update();
            });
        }
    }

    resetView() {
        if (!this._initialCameraPos) return;
        const startPos = this.camera.position.clone();
        const startTarget = this.controls.target.clone();
        const endPos = this._initialCameraPos.clone();
        const endTarget = this._initialTarget.clone();

        let t = 0;
        const step = () => {
            t += 0.05;
            if (t >= 1) {
                this.camera.position.copy(endPos);
                this.controls.target.copy(endTarget);
                this.controls.update();
                return;
            }
            const ease = t * t * (3 - 2 * t);
            this.camera.position.lerpVectors(startPos, endPos, ease);
            this.controls.target.lerpVectors(startTarget, endTarget, ease);
            this.controls.update();
            requestAnimationFrame(step);
        };
        step();
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.container.requestFullscreen?.() ||
            this.container.webkitRequestFullscreen?.();
        } else {
            document.exitFullscreen?.() ||
            document.webkitExitFullscreen?.();
        }
    }

    _handleResize() {
        if (!this.renderer || !this.camera || !this.container) return;
        const width = this.container.clientWidth || 800;
        const height = Math.max(this.container.clientHeight || 400, 400);

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    _setupVisibilityObserver() {
        if (!('IntersectionObserver' in window)) return;
        this._observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    const wasVisible = this._isVisible;
                    this._isVisible = entry.isIntersecting;
                    if (!wasVisible && this._isVisible && !this.disposed) {
                        this._animate();
                    }
                });
            },
            { threshold: 0.02, rootMargin: '100px' }
        );
        this._observer.observe(this.container);
    }

    _animate() {
        if (this.disposed) return;
        if (!this._isVisible) {
            this.animationId = null;
            return;
        }

        this.animationId = requestAnimationFrame(() => this._animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    dispose() {
        this.disposed = true;
        if (this.animationId) cancelAnimationFrame(this.animationId);
        if (this._observer) this._observer.disconnect();
        if (this._onResize) window.removeEventListener('resize', this._onResize);
        if (this.controls) this.controls.dispose();
        if (this.renderer) {
            this.renderer.dispose();
            this.renderer.domElement?.remove();
        }
        if (this.scene) {
            this.scene.traverse(obj => {
                if (obj.isSprite && obj.material) {
                    if (obj.material.map) obj.material.map.dispose();
                    obj.material.dispose();
                }
            });
        }
    }
}

/* ================================================================
   AUTO-INITIALISATION
   ================================================================ */

function initSolarVisualizer() {
    const container = document.getElementById('solar-3d-container');
    if (!container || window._solar3d) return;
    try {
        window._solar3d = new SolarVisualizer('solar-3d-container', 'solar-3d-data');
    } catch (e) {
        console.error('[Solar3D] Fatal error instantiating visualizer:', e);
        const loading = container.querySelector('.solar-3d-loading');
        if (loading) loading.style.display = 'none';
        const fallback = container.querySelector('.solar-3d-fallback');
        if (fallback) {
            fallback.style.display = 'flex';
            const msg = fallback.querySelector('.solar-3d-fallback-msg');
            if (msg) msg.textContent = 'Interactive 3D preview encountered an initialization error.';
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSolarVisualizer);
} else {
    initSolarVisualizer();
}

export { SolarVisualizer };
