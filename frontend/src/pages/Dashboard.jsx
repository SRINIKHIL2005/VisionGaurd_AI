import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Shield, Eye, Users, Activity, Camera,
  Image as ImageIcon, Video, Zap, Brain,
  Target, Bell, Mic, CheckCircle, AlertTriangle,
  ArrowRight, Cpu, Database, CloudLightning
} from "lucide-react";
import axios from "axios";
import authService from '../services/authService';

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, delay },
});

function StatusDot({ ok, loading }) {
  if (loading) return <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block" />;
  return ok
    ? <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
    : <span className="w-2.5 h-2.5 rounded-full bg-red-400 inline-block" />;
}

function ModelBadge({ ok, loading }) {
  if (loading) return <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-700 text-slate-400">...</span>;
  return ok
    ? <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">LOADED</span>
    : <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-500/15 text-red-400 border border-red-500/30">OFFLINE</span>;
}

const STEPS = [
  {
    num: "01",
    icon: Camera,
    title: "Capture",
    desc: "Feed comes in from a live camera, an uploaded image, or a video file.",
    color: "blue",
  },
  {
    num: "02",
    icon: Cpu,
    title: "Analyse",
    desc: "Three AI models run in parallel — deepfake check, face match, and object scan.",
    color: "purple",
  },
  {
    num: "03",
    icon: Bell,
    title: "Alert",
    desc: "A risk score is calculated and a Telegram alert fires if anything serious is found.",
    color: "cyan",
  },
];

const FEATURES = [
  {
    href: "/image",
    icon: ImageIcon,
    label: "Upload & Analyse",
    title: "Image Analysis",
    desc: "Upload any image and get a full breakdown — deepfake check, face recognition, and object detection all in one pass.",
    tags: ["Deepfake Check", "Face ID", "Object Scan"],
    accent: "from-blue-600 to-indigo-700",
    dot: "bg-blue-400",
  },
  {
    href: "/video",
    icon: Video,
    label: "Frame by Frame",
    title: "Video Analysis",
    desc: "Upload a video and the system samples frames, builds a risk timeline, and gives you a full statistics summary.",
    tags: ["Timeline Chart", "Risk Stats", "Frame Skip"],
    accent: "from-violet-600 to-purple-700",
    dot: "bg-violet-400",
  },
  {
    href: "/live",
    icon: Camera,
    label: "Live",
    title: "CCTV Monitoring",
    desc: "Watch your webcam in real time with AI running on every frame, instant threat overlays, and automatic alerts.",
    tags: ["Real-Time", "Auto Alerts", "Live Overlay"],
    accent: "from-rose-600 to-red-700",
    dot: "bg-rose-400",
    live: true,
  },
  {
    href: "/database",
    icon: Users,
    label: null,
    title: "Face Database",
    desc: "Register people by photo. The system learns their face and flags anyone who is not on the approved list.",
    tags: ["Add Identity", "Upload Photo", "Manage All"],
    accent: "from-emerald-600 to-teal-700",
    dot: "bg-emerald-400",
  },
];

const MODELS = [
  {
    icon: Brain,
    name: "Deepfake Detection",
    detail: "Gemini 2.0 Flash for images · HuggingFace ViT for video",
    sub: "dima806/deepfake_vs_real_image_detection",
    key: "deepfake_detector",
    color: "text-blue-400",
    border: "border-blue-500/20",
    bg: "bg-blue-500/8",
  },
  {
    icon: Eye,
    name: "Face Recognition",
    detail: "InsightFace ArcFace r100 · per-user database",
    sub: "Similarity threshold 0.5 · unknown face queuing",
    key: "face_recognizer",
    color: "text-purple-400",
    border: "border-purple-500/20",
    bg: "bg-purple-500/8",
  },
  {
    icon: Target,
    name: "Object & Weapon Detection",
    detail: "YOLOv8 Nano · custom weapon detector (best.pt)",
    sub: "ROI weapon scan · 80+ object classes · IOU tracker",
    key: "object_detector",
    color: "text-cyan-400",
    border: "border-cyan-500/20",
    bg: "bg-cyan-500/8",
  },
];

const STACK = [
  { label: "Backend", items: ["FastAPI (Python)", "PyTorch + Transformers", "InsightFace · Ultralytics YOLOv8", "FAISS vector store · MongoDB Atlas"] },
  { label: "Frontend", items: ["React 18 + Vite", "Tailwind CSS · Framer Motion", "React Router v6 · Lucide Icons", "Axios for API calls"] },
  { label: "AI / APIs", items: ["Google Gemini 2.0 Flash", "HuggingFace Hub (ViT model)", "Microsoft Edge TTS (neural voices)", "Telegram Bot API"] },
];

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [faceCount, setFaceCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const authAxios = authService.getAuthAxios();
        const [hRes, fRes] = await Promise.all([
          axios.get("/health"),
          authAxios.get("/face/list"),
        ]);
        setHealth(hRes.data);
        setFaceCount(fRes.data?.identities?.length ?? 0);
      } catch (e) {
        console.error("Dashboard data fetch failed:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const ml = health?.models_loaded ?? {};
  const allOnline = !loading && ml.deepfake_detector && ml.face_recognizer && ml.object_detector;

  return (
    <div className="min-h-screen bg-[#04080f] text-white px-6 py-8 space-y-10">

      {/* ── HERO ──────────────────────────────────────────────── */}
      <motion.div {...fadeUp(0)} className="relative rounded-3xl overflow-hidden border border-slate-800/60 bg-[#060c18]">
        {/* Background decoration */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-60px] left-[-40px] w-96 h-96 bg-blue-700/10 rounded-full blur-[120px]" />
          <div className="absolute bottom-0 right-0 w-72 h-72 bg-cyan-600/6 rounded-full blur-[100px]" />
          <div
            className="absolute inset-0 opacity-[0.025]"
            style={{
              backgroundImage: "linear-gradient(rgba(59,130,246,1) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,1) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
          />
        </div>

        <div className="relative z-10 px-10 py-12">
          {/* Logo row */}
          <div className="flex items-center gap-4 mb-8">
            <motion.div
              animate={{ boxShadow: ["0 0 10px rgba(59,130,246,0.3)", "0 0 28px rgba(59,130,246,0.6)", "0 0 10px rgba(59,130,246,0.3)"] }}
              transition={{ duration: 2.5, repeat: Infinity }}
              className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center flex-shrink-0"
            >
              <Shield className="w-7 h-7 text-white" />
            </motion.div>
            <div>
              <h1 style={{ fontFamily: "'Dancing Script', cursive" }} className="text-5xl font-bold text-white leading-none">VisionGuard AI</h1>
              <p className="text-blue-400 text-sm font-semibold uppercase tracking-widest mt-1">Real-Time Security Intelligence</p>
            </div>
          </div>

          <p className="text-slate-300 text-lg leading-relaxed max-w-2xl mb-10">
            An AI surveillance platform that watches your cameras, detects threats in real time,
            recognises faces, and instantly alerts you — all managed through one dashboard and
            controlled by a voice assistant.
          </p>

          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              {
                label: "System Status",
                value: loading ? "..." : allOnline ? "All Online" : "Partial",
                icon: <StatusDot ok={allOnline} loading={loading} />,
                color: "border-emerald-500/25 bg-emerald-500/5",
              },
              {
                label: "AI Models Loaded",
                value: loading ? "..." : `${Object.values(ml).filter(Boolean).length} / 3`,
                icon: <Cpu className="w-4 h-4 text-blue-400" />,
                color: "border-blue-500/25 bg-blue-500/5",
              },
              {
                label: "Registered Faces",
                value: loading ? "..." : faceCount,
                icon: <Users className="w-4 h-4 text-purple-400" />,
                color: "border-purple-500/25 bg-purple-500/5",
              },
            ].map(({ label, value, icon, color }) => (
              <div key={label} className={`rounded-2xl border p-6 ${color}`}>
                <div className="flex items-center gap-2 mb-3">
                  {icon}
                  <span className="text-slate-400 text-sm">{label}</span>
                </div>
                <p className="text-3xl font-bold text-white">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* ── HOW IT WORKS ──────────────────────────────────────── */}
      <motion.div {...fadeUp(0.1)}>
        <h2 className="text-2xl font-bold text-white mb-6">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STEPS.map(({ num, icon: Icon, title, desc, color }) => (
            <div key={num} className="relative bg-[#060c18] border border-slate-800/60 rounded-2xl p-6">
              <p className={`text-5xl font-black text-${color}-600/20 absolute top-4 right-5 leading-none select-none`}>{num}</p>
              <div className={`w-11 h-11 rounded-xl bg-${color}-600/15 border border-${color}-500/25 flex items-center justify-center mb-4`}>
                <Icon className={`w-5 h-5 text-${color}-400`} />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* ── AI MODELS + FEATURE CARDS ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* AI Models */}
        <motion.div {...fadeUp(0.15)} className="bg-[#060c18] border border-slate-800/60 rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-blue-600/15 border border-blue-500/25 flex items-center justify-center">
              <Brain className="w-5 h-5 text-blue-400" />
            </div>
            <h2 className="text-xl font-bold text-white">AI Models</h2>
          </div>

          <div className="space-y-4">
            {MODELS.map(({ icon: Icon, name, detail, sub, key, color, border, bg }) => (
              <div key={key} className={`rounded-xl border ${border} ${bg} p-5`}>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-3">
                    <Icon className={`w-5 h-5 ${color} flex-shrink-0 mt-0.5`} />
                    <p className="text-white font-semibold">{name}</p>
                  </div>
                  <ModelBadge ok={ml[key]} loading={loading} />
                </div>
                <p className="text-slate-300 text-sm ml-8">{detail}</p>
                <p className="text-slate-500 text-xs ml-8 mt-1">{sub}</p>
              </div>
            ))}

            {/* Jarvis */}
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-5">
              <div className="flex items-center gap-3 mb-2">
                <Mic className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                <p className="text-white font-semibold">Jarvis — Voice Assistant</p>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">ACTIVE</span>
              </div>
              <p className="text-slate-300 text-sm ml-8">Gemini 2.0 Flash · FAISS RAG · Edge TTS neural voices</p>
              <p className="text-slate-500 text-xs ml-8 mt-1">Say "Hey Jarvis" · answers from real detection logs · controls the UI by voice</p>
            </div>
          </div>
        </motion.div>

        {/* Feature Cards */}
        <motion.div {...fadeUp(0.2)} className="space-y-4">
          <h2 className="text-xl font-bold text-white">Features</h2>
          <div className="space-y-3">
            {FEATURES.map(({ href, icon: Icon, label, title, desc, tags, accent, dot, live }) => (
              <Link key={href} to={href}>
                <motion.div
                  whileHover={{ x: 4 }}
                  className={`bg-gradient-to-r ${accent} rounded-2xl p-5 cursor-pointer`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <Icon className="w-6 h-6 text-white" />
                      <h3 className="text-lg font-bold text-white">{title}</h3>
                    </div>
                    {live ? (
                      <span className="flex items-center gap-1.5 px-3 py-1 bg-white/20 rounded-full text-xs font-semibold text-white">
                        <span className="w-1.5 h-1.5 bg-red-300 rounded-full animate-pulse" />
                        Live
                      </span>
                    ) : label ? (
                      <span className="px-3 py-1 bg-white/20 rounded-full text-xs font-semibold text-white">{label}</span>
                    ) : (
                      <span className="px-3 py-1 bg-white/20 rounded-full text-xs font-semibold text-white">{faceCount} registered</span>
                    )}
                  </div>
                  <p className="text-white/70 text-sm leading-relaxed mb-3">{desc}</p>
                  <div className="flex flex-wrap gap-2">
                    {tags.map((t) => (
                      <span key={t} className="flex items-center gap-1.5 text-xs text-white/70">
                        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />{t}
                      </span>
                    ))}
                  </div>
                </motion.div>
              </Link>
            ))}
          </div>
        </motion.div>
      </div>

      {/* ── TECH STACK + STATS ────────────────────────────────── */}
      <motion.div {...fadeUp(0.25)} className="bg-[#060c18] border border-slate-800/60 rounded-2xl p-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-slate-700/50 border border-slate-600/40 flex items-center justify-center">
            <Zap className="w-5 h-5 text-yellow-400" />
          </div>
          <h2 className="text-xl font-bold text-white">Tech Stack & Numbers</h2>
        </div>

        {/* Numbers */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { val: "3", label: "AI Models", icon: Brain, color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
            { val: "80+", label: "Object Classes", icon: Target, color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
            { val: "< 0.3s", label: "Alert Speed", icon: CloudLightning, color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" },
            { val: "24/7", label: "Monitoring Ready", icon: Shield, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
          ].map(({ val, label, icon: Icon, color }) => (
            <div key={label} className={`rounded-xl border p-5 text-center ${color.split(" ").slice(1).join(" ")}`}>
              <Icon className={`w-7 h-7 mx-auto mb-2 ${color.split(" ")[0]}`} />
              <p className={`text-3xl font-black ${color.split(" ")[0]}`}>{val}</p>
              <p className="text-slate-400 text-xs mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* Stack columns */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {STACK.map(({ label, items }) => (
            <div key={label} className="bg-slate-800/30 border border-slate-700/40 rounded-xl p-5">
              <p className="text-slate-300 font-semibold text-sm mb-3 uppercase tracking-wider">{label}</p>
              <ul className="space-y-2">
                {items.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm text-slate-400">
                    <CheckCircle className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </motion.div>

    </div>
  );
}