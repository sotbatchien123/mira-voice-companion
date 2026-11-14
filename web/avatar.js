import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { SyllableTracker, VISEMES, syllableVisemes } from "./lipsync.js";

/** Tên expression chuẩn VRM 1.0, khớp với app/emotion_tags.py */
export const EMOTIONS = ["neutral", "happy", "angry", "sad", "relaxed", "surprised"];

/** Sau bao lâu không có cảm xúc mới thì mặt dịu về neutral (giây). */
const EMOTION_HOLD_SEC = 6;

/** Dáng đầu theo cảm xúc (rad): x > 0 cúi xuống, z > 0 nghiêng sang trái màn hình. Biên độ nhỏ để không lố. */
const POSES = {
  neutral: { x: 0, z: 0 },
  happy: { x: -0.03, z: 0.07 },
  sad: { x: 0.12, z: -0.03 },
  surprised: { x: -0.08, z: 0 },
  angry: { x: 0.06, z: 0 },
  relaxed: { x: 0.02, z: -0.06 },
};
const LISTENING_POSE = { x: 0.04, z: 0.1 }; // nghiêng đầu "lắng nghe" khi người dùng đang nói

/**
 * Quản lý scene 3D + model VRM: idle (thở, chớp mắt, lắc đầu nhẹ),
 * biểu cảm theo tag và khẩu hình giả lập khi đang "nói".
 */
export class Avatar {
  /** @param {HTMLElement} container */
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.timer = new THREE.Timer();
    this.loader = new GLTFLoader();
    this.loader.register((parser) => new VRMLoaderPlugin(parser));
    /** @type {import("@pixiv/three-vrm").VRM | null} */
    this.vrm = null;

    this.elapsed = 0;
    this.emotion = "neutral";
    this.emotionAge = 0;
    this.weights = new Map(EMOTIONS.map((e) => [e, 0]));
    this.nextBlink = 2;
    this.blinkT = -1;
    this.talking = false;
    this.mouth = 0;
    /** Âm lượng audio đang phát (0..1) hoặc null nếu không có giọng thật. */
    this.audioLevel = null;
    /** Đỉnh âm lượng gần đây, để tự cân: giọng to hay nhỏ (Piper ~0.45, VieNeu ~0.2) đều nhép miệng như nhau. */
    this.levelPeak = 0.15;
    // Nhép miệng theo nguyên âm: khẩu hình của từng âm tiết, đổi khi bắt được nhịp âm tiết mới trong audio
    this.tracker = new SyllableTracker();
    this.visemes = [];
    this.syllable = -1;
    this.viseme = "aa";
    this.visemeWeights = new Map(VISEMES.map((v) => [v, 0]));
    this.syllableCount = 0; // đếm để kiểm chứng (so với số âm tiết trong chữ)
    // Cử động đầu
    this.nod = 0;
    this.listening = false;
    this.pose = { x: 0, z: 0 };

    // ?debug=1: lộ avatar ra window để đo trong lúc kiểm chứng (không bật thì không có gì)
    if (new URLSearchParams(location.search).has("debug")) window.__mira = { avatar: this };

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
    this.camera.position.set(0, 1.35, 1.6);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 1.3, 0);
    this.controls.enableDamping = true;
    this.controls.update();

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8888aa, 1.2));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(1, 2, 2);
    this.scene.add(key);

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.renderer.setAnimationLoop((t) => this.tick(t));
  }

  /** Nạp model từ URL (vd /models/waifu.vrm) hoặc từ File người dùng kéo thả. */
  async load(source) {
    const url = typeof source === "string" ? source : URL.createObjectURL(source);
    try {
      const gltf = await this.loader.loadAsync(url);
      const vrm = gltf.userData.vrm;
      if (!vrm) throw new Error("File này không phải model VRM hợp lệ");

      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.combineSkeletons(gltf.scene);
      VRMUtils.rotateVRM0(vrm); // model VRM 0.x quay mặt ngược, xoay lại cho đúng

      if (this.vrm) {
        this.scene.remove(this.vrm.scene);
        VRMUtils.deepDispose(this.vrm.scene);
      }
      this.vrm = vrm;
      this.scene.add(vrm.scene);
      if (vrm.lookAt) vrm.lookAt.target = this.camera; // mắt nhìn theo camera
      this.relaxArms();
      this.frameFace();
    } finally {
      if (typeof source !== "string") URL.revokeObjectURL(url);
    }
  }

  setEmotion(emotion) {
    if (!EMOTIONS.includes(emotion)) return;
    this.emotion = emotion;
    this.emotionAge = 0;
  }

  /** Bật/tắt khẩu hình giả lập (dùng khi tắt giọng nói). */
  setTalking(on) {
    this.talking = on;
  }

  /** Miệng theo âm lượng audio thật; null để quay về khẩu hình giả lập / khép miệng. */
  setMouthLevel(level) {
    this.audioLevel = level;
  }

  /** Chữ của đoạn vừa bắt đầu đọc: tách thành khẩu hình từng âm tiết. */
  setSpeechText(text) {
    this.visemes = syllableVisemes(text ?? "");
    this.syllable = -1;
  }

  /** Người dùng đang nói vào mic: Mira nghiêng đầu lắng nghe. */
  setListening(on) {
    this.listening = on;
  }

  /** Hạ tay từ tư thế chữ T xuống cạnh người. */
  relaxArms() {
    const h = this.vrm?.humanoid;
    if (!h) return;
    const l = h.getNormalizedBoneNode("leftUpperArm");
    const r = h.getNormalizedBoneNode("rightUpperArm");
    if (l) l.rotation.z = -1.2;
    if (r) r.rotation.z = 1.2;
  }

  /** Đặt camera nhìn vào mặt, dù model cao hay thấp. */
  frameFace() {
    const head = this.vrm?.humanoid?.getNormalizedBoneNode("head");
    if (!head) return;
    this.vrm.scene.updateMatrixWorld(true);
    const p = head.getWorldPosition(new THREE.Vector3());
    this.controls.target.set(0, p.y - 0.05, 0);
    this.camera.position.set(0, p.y, 1.4);
    this.controls.update();
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  tick(timestamp) {
    this.timer.update(timestamp);
    const dt = Math.min(this.timer.getDelta(), 0.1);
    this.elapsed += dt;
    this.controls.update();
    if (this.vrm) {
      this.animateIdle(dt);
      this.animateFace(dt);
      this.vrm.update(dt); // cập nhật expression, lookAt, vật lý tóc/váy (spring bone)
    }
    this.renderer.render(this.scene, this.camera);
  }

  animateIdle(dt) {
    const h = this.vrm.humanoid;
    const t = this.elapsed;
    const spine = h.getNormalizedBoneNode("spine");
    const neck = h.getNormalizedBoneNode("neck");
    const head = h.getNormalizedBoneNode("head");
    if (spine) spine.rotation.x = Math.sin(t * 1.6) * 0.015; // thở

    // Dáng theo cảm xúc (+ lắng nghe), chuyển mượt; gật nhẹ theo nhịp âm tiết khi đang nói
    const base = POSES[this.emotion] ?? POSES.neutral;
    const target = this.listening ? { x: base.x + LISTENING_POSE.x, z: base.z + LISTENING_POSE.z } : base;
    this.pose.x = THREE.MathUtils.damp(this.pose.x, target.x, 3, dt);
    this.pose.z = THREE.MathUtils.damp(this.pose.z, target.z, 3, dt);
    this.nod = THREE.MathUtils.damp(this.nod, 0, 10, dt);

    // Chia cho cổ và đầu để cử động trông liền mạch
    if (neck) {
      neck.rotation.x = this.pose.x * 0.4;
      neck.rotation.y = Math.sin(t * 0.5) * 0.06;
      neck.rotation.z = Math.sin(t * 0.37) * 0.03 + this.pose.z * 0.4;
    }
    if (head) {
      head.rotation.x = this.pose.x * 0.6 + this.nod;
      head.rotation.z = this.pose.z * 0.6;
    }
  }

  animateFace(dt) {
    const em = this.vrm.expressionManager;
    if (!em) return;

    // Cảm xúc: tự dịu về neutral sau một lúc
    this.emotionAge += dt;
    const speaking = this.talking || this.audioLevel !== null;
    if (this.emotion !== "neutral" && this.emotionAge > EMOTION_HOLD_SEC && !speaking) {
      this.emotion = "neutral";
    }
    for (const e of EMOTIONS) {
      if (e === "neutral") continue;
      const target = e === this.emotion ? 0.8 : 0;
      const w = THREE.MathUtils.damp(this.weights.get(e), target, 6, dt);
      this.weights.set(e, w);
      em.setValue(e, w);
    }

    // Chớp mắt ngẫu nhiên mỗi 2-6 giây
    if (this.blinkT < 0 && this.elapsed > this.nextBlink) this.blinkT = 0;
    let blink = 0;
    if (this.blinkT >= 0) {
      this.blinkT += dt;
      blink = Math.sin(Math.min(this.blinkT / 0.15, 1) * Math.PI);
      if (this.blinkT > 0.15) {
        this.blinkT = -1;
        this.nextBlink = this.elapsed + 2 + Math.random() * 4;
      }
    }
    // Đang cười tươi thì mắt đã híp, giảm blink để không bị méo
    em.setValue("blink", blink * (1 - this.weights.get("happy") * 0.6));

    // Có giọng thật: miệng theo âm lượng chia cho đỉnh gần đây (đỉnh hạ dần 0.02/giây).
    // Đo được: trung vị ≈ 0.4-0.55 lần đỉnh -> miệng mở ~0.3-0.45, câu to mở ~0.6-0.7. Không có giọng: nhịp giả lập
    let target = 0;
    if (this.audioLevel !== null) {
      this.levelPeak = Math.max(this.audioLevel, this.levelPeak - 0.02 * dt, 0.05);
      target = Math.min(0.9, Math.max(0, (this.audioLevel / this.levelPeak - 0.15) * 1.1));
    }
    else if (this.talking) target = 0.25 + 0.35 * Math.abs(Math.sin(this.elapsed * 14)) * Math.random();
    this.mouth = THREE.MathUtils.damp(this.mouth, target, 18, dt);

    // Khẩu hình: có giọng thật thì theo nguyên âm của âm tiết hiện tại; không thì chỉ "aa" như trước
    if (this.audioLevel !== null) {
      if (this.tracker.update(this.audioLevel, dt)) {
        this.syllable = Math.min(this.syllable + 1, Math.max(this.visemes.length - 1, 0));
        this.viseme = this.visemes[this.syllable] ?? "aa";
        this.syllableCount += 1;
        this.nod = 0.035; // gật nhẹ đầu mỗi âm tiết
      }
    } else {
      this.viseme = "aa";
    }
    for (const v of VISEMES) {
      const w = THREE.MathUtils.damp(this.visemeWeights.get(v), v === this.viseme ? this.mouth : 0, 20, dt);
      this.visemeWeights.set(v, w);
      em.setValue(v, w);
    }
  }
}
