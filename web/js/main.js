import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

// --- 初始化场景 ---
const scene = new THREE.Scene();

// 视线目标
const lookAtTarget = new THREE.Object3D();
lookAtTarget.position.set(0, 1.5, 2);
scene.add(lookAtTarget);

// 相机
const camera = new THREE.PerspectiveCamera(30, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.0, 2.0);
camera.lookAt(0, 1.0, 0);

// 一个极弱的方向光，仅用于给 MToon 提供基础亮度
const softLight = new THREE.DirectionalLight(0xffffff, 1);
softLight.position.set(0.5, 1, 1);
scene.add(softLight);

// 渲染器
const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "high-performance"
});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.9;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

// --- 加载 HDR 环境贴图 ---
const rgbeLoader = new RGBELoader();
rgbeLoader.load('./lib/hdri/studio.hdr', (texture) => {
    texture.mapping = THREE.EquirectangularReflectionMapping;
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const envMap = pmremGenerator.fromEquirectangular(texture).texture;
    scene.environment = envMap;
    scene.environmentIntensity = 2.0;   // 【关键】环境光更强
    texture.dispose();
    pmremGenerator.dispose();

    console.log('HDR 环境贴图加载成功');
}, undefined, (err) => {
    console.error('HDR 加载失败，回退到默认光照:', err);
    // 回退方案：如果 HDR 加载失败，用 RoomEnvironment 兜底
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new THREE.Scene(), 0.04).texture;
});

// --- 加载 VRM 模型 ---
let vrm = null;
const loader = new GLTFLoader();
loader.register((parser) => new VRMLoaderPlugin(parser));

loader.load('./models/your_model.vrm', (gltf) => {
    vrm = gltf.userData.vrm;

    if (vrm.lookAt) {
        vrm.lookAt.target = lookAtTarget;
    }
    scene.add(vrm.scene);

    // 位置、缩放、朝向
    vrm.scene.position.set(0, 0, 0);
    vrm.scene.scale.set(0.8, 0.8, 0.8);
    vrm.scene.rotation.y = Math.PI;

    console.log('VRM模型加载成功！');
    console.log("模型支持的表情列表:");
    for (const name in vrm.expressionManager.expressions) {
        console.log("  -", name);
    }

    // 手臂自然下垂
    if (vrm.humanoid) {
        const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
        const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
        if (leftUpperArm) leftUpperArm.rotation.z = 1.2;
        if (rightUpperArm) rightUpperArm.rotation.z = -1.2;
    }

    // 阴影 + MToon 材质调整
    vrm.scene.traverse((obj) => {
        if (obj.isMesh) {
            obj.castShadow = true;
            obj.receiveShadow = true;
            obj.frustumCulled = false;

            const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
            mats.forEach((mat) => {
                if (!mat) return;

                // 有些模型用的是 MToon，有些用的是其他材质
                if (mat.isMToonMaterial) {
                    // 卡通程度，0.8 保留一点动漫感，但比默认更自然
                    if ('shadingToony' in mat) mat.shadingToony = 0.8;
                    if ('shadingShift' in mat) mat.shadingShift = -0.1;

                    // 关掉边缘描边光
                    if ('rimLighting' in mat) mat.rimLighting = false;

                    // 关掉或减细描边
                    if ('outlineWidthMode' in mat) mat.outlineWidthMode = 'none';
                    if ('outlineWidth' in mat) mat.outlineWidth = 0;
                }

                // 不管什么材质，都提升一点反射
                if ('envMapIntensity' in mat) mat.envMapIntensity = 1.0;
            });
        }
    });
}, (progress) => {
    console.log('加载中...', (progress.loaded / progress.total * 100).toFixed(1) + '%');
}, (error) => {
    console.error('加载模型失败:', error);
});

// --- 眨眼控制器 ---
const clock = new THREE.Clock();
let blinkTime = 0;
let nextBlinkDelay = 2 + Math.random() * 3;
let isBlinking = false;
let blinkProgress = 0;

function updateBlink(delta) {
    if (!vrm || !vrm.expressionManager) return;
    blinkTime += delta;

    if (!isBlinking) {
        if (blinkTime >= nextBlinkDelay) {
            isBlinking = true;
            blinkProgress = 0;
            blinkTime = 0;
        }
    } else {
        blinkProgress += delta / 0.15;
        let value;
        if (blinkProgress < 0.5) {
            value = blinkProgress * 2;
        } else {
            value = (1 - blinkProgress) * 2;
        }
        vrm.expressionManager.setValue('blink', Math.max(0, Math.min(1, value)));
        if (blinkProgress >= 1) {
            isBlinking = false;
            nextBlinkDelay = 2 + Math.random() * 3;
            vrm.expressionManager.setValue('blink', 0);
        }
    }
}

// --- 动画循环 ---
function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();

    if (vrm) {
        const time = Date.now() * 0.001;

        // 呼吸
        vrm.scene.position.y = Math.sin(time * 1.8) * 0.008;
        vrm.scene.position.z = Math.sin(time * 1.2) * 0.005;

        // 身体微摆
        vrm.scene.rotation.z = Math.sin(time * 0.6) * 0.01;

        // 头部自然晃动
        const head = vrm.humanoid?.getNormalizedBoneNode('head');
        if (head) {
            head.rotation.y = Math.sin(time * 0.4) * 0.08;
            head.rotation.z = Math.sin(time * 0.7) * 0.04 + Math.sin(time * 0.2) * 0.03;
            head.rotation.x = Math.sin(time * 0.5) * 0.02;
        }

        updateBlink(delta);
        vrm.update(delta);
    }
    renderer.render(scene, camera);
}
animate();

// --- 窗口大小自适应 ---
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- 与 Python 通信 ---
window.setEmotion = (emotionName) => {
    console.log("JS 收到表情指令:", emotionName);
    if (!vrm || !vrm.expressionManager) return;

    const expressionMap = {
        'happy': 'happy',
        'sad': 'sad',
        'angry': 'angry',
        'surprised': 'surprised',
        'neutral': ''
    };

    vrm.expressionManager.resetValues();
    const targetExpression = expressionMap[emotionName];
    if (targetExpression && targetExpression !== 'neutral') {
        vrm.expressionManager.setValue(targetExpression, 1.0);
    }
    console.log(`设置表情: ${emotionName}`);
};

let bubbleText = '';
window.appendText = (text) => {
    bubbleText += text;
    const bubble = document.getElementById('chat-bubble');
    bubble.style.display = 'block';
    bubble.innerText = bubbleText;
};
window.clearText = () => {
    bubbleText = '';
    document.getElementById('chat-bubble').innerText = '';
    document.getElementById('chat-bubble').style.display = 'none';
};

window.setAffection = (value) => {
    const fill = document.getElementById('affection-fill');
    const label = document.getElementById('affection-value');
    if (fill) fill.style.width = Math.max(0, Math.min(100, value)) + '%';
    if (label) label.textContent = value;
};

// --- Python 桥接 ---
new QWebChannel(qt.webChannelTransport, function(channel) {
    window.bridge = channel.objects.bridge;
    console.log("Python通信桥接成功");
});

// --- 输入框 ---
const inputElement = document.getElementById('chat-input');
if (inputElement) {
    inputElement.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            const text = inputElement.value.trim();
            if (text && window.bridge) {
                window.bridge.sendMessage(text);
                inputElement.value = '';
            }
        }
    });
}

// --- 鼠标跟随视线 ---
window.addEventListener('mousemove', (event) => {
    const x = (event.clientX / window.innerWidth) * 2 - 1;
    const y = -(event.clientY / window.innerHeight) * 2 + 1;
    lookAtTarget.position.set(x * 1.5, y * 1.5 + 1.4, 2);
});