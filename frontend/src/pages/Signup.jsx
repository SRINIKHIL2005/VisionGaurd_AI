import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mail, Lock, Eye, EyeOff, AlertCircle,
  Shield, Camera, Users, Bell, ArrowRight,
  User, CheckCircle
} from "lucide-react";
import authService from "../services/authService";

const FEATURES = [
  {
    icon: Camera,
    title: "Live Camera Monitoring",
    desc: "Watch all your camera feeds with AI analysis running on every frame in real time.",
  },
  {
    icon: Shield,
    title: "Automatic Threat Detection",
    desc: "Weapons, suspicious behaviour, and manipulated media are flagged immediately.",
  },
  {
    icon: Users,
    title: "Face Recognition",
    desc: "Identifies known team members and flags anyone not on your approved list.",
  },
  {
    icon: Bell,
    title: "Instant Alerts",
    desc: "Get a Telegram notification within seconds whenever something is detected.",
  },
];

function FeatureItem({ icon: Icon, title, desc, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.25 + index * 0.08, duration: 0.4 }}
      whileHover={{ x: 6 }}
      className="flex gap-4 p-4 rounded-xl hover:bg-blue-500/5 transition-colors cursor-default"
    >
      <div className="w-11 h-11 rounded-xl bg-blue-600/15 border border-blue-500/25 flex items-center justify-center flex-shrink-0">
        <Icon className="w-5 h-5 text-blue-400" />
      </div>
      <div>
        <p className="text-white font-semibold text-base mb-1">{title}</p>
        <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
      </div>
    </motion.div>
  );
}

const STRENGTH_LABELS = ["", "Weak", "Fair", "Good", "Strong", "Excellent"];
const STRENGTH_COLORS = ["", "bg-red-500", "bg-orange-500", "bg-yellow-500", "bg-blue-500", "bg-emerald-500"];

function PasswordStrengthBar({ strength }) {
  return (
    <div className="mt-3">
      <div className="flex gap-1.5 mb-1.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <motion.div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
              i <= strength ? STRENGTH_COLORS[strength] : "bg-slate-700"
            }`}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: i * 0.04 }}
          />
        ))}
      </div>
      {strength > 0 && (
        <p className={`text-xs font-medium ${
          strength <= 2 ? "text-red-400" : strength <= 3 ? "text-yellow-400" : "text-emerald-400"
        }`}>
          {STRENGTH_LABELS[strength]} password
        </p>
      )}
    </div>
  );
}

function Signup() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState(0);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError("");
    if (name === "password") {
      let s = 0;
      if (value.length >= 8) s++;
      if (/[A-Z]/.test(value)) s++;
      if (/[a-z]/.test(value)) s++;
      if (/[0-9]/.test(value)) s++;
      if (/[^A-Za-z0-9]/.test(value)) s++;
      setPasswordStrength(s);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.fullName.trim()) { setError("Full name is required"); return; }
    if (!formData.email.includes("@")) { setError("Enter a valid email address"); return; }
    if (formData.password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (formData.password !== formData.confirmPassword) { setError("Passwords do not match"); return; }

    setLoading(true);
    const result = await authService.register(formData.email, formData.password, formData.fullName);
    if (result.success) {
      navigate("/");
    } else {
      setError(result.error || "Something went wrong. Please try again.");
    }
    setLoading(false);
  };

  const passwordsMatch =
    formData.confirmPassword.length > 0 &&
    formData.password === formData.confirmPassword;

  return (
    <div className="min-h-screen flex bg-[#04080f]">
      {/* LEFT panel */}
      <div className="hidden lg:flex flex-col justify-between w-[52%] bg-[#060c18] px-16 py-14 border-r border-slate-800/60 relative overflow-hidden">
        {/* Background glow blobs */}
        <div className="absolute top-[-120px] left-[-80px] w-[420px] h-[420px] bg-blue-700/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-80px] right-[-60px] w-[320px] h-[320px] bg-cyan-600/6 rounded-full blur-[100px] pointer-events-none" />

        {/* Animated orbit ring */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03]">
          <motion.svg
            width="700"
            height="700"
            viewBox="0 0 700 700"
            animate={{ rotate: 360 }}
            transition={{ duration: 90, repeat: Infinity, ease: "linear" }}
          >
            <circle cx="350" cy="350" r="280" stroke="#3b82f6" strokeWidth="1" fill="none" strokeDasharray="8 20" />
            <circle cx="350" cy="350" r="180" stroke="#22d3ee" strokeWidth="1" fill="none" strokeDasharray="4 18" />
          </motion.svg>
        </div>

        {/* Scan line */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div
            className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/20 to-transparent"
            initial={{ top: "-2px" }}
            animate={{ top: "102%" }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear", repeatDelay: 2 }}
          />
        </div>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <motion.div
            animate={{
              boxShadow: [
                "0 0 12px rgba(59,130,246,0.3)",
                "0 0 28px rgba(59,130,246,0.65)",
                "0 0 12px rgba(59,130,246,0.3)",
              ],
            }}
            transition={{ duration: 2.5, repeat: Infinity }}
            className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center"
          >
            <Shield className="w-6 h-6 text-white" />
          </motion.div>
          <div>
            <p className="text-white font-bold text-xl leading-none">VisionGuard</p>
            <p className="text-blue-400 text-xs font-semibold tracking-widest uppercase">AI Security</p>
          </div>
        </div>

        {/* Hero content */}
        <div className="relative z-10">
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-blue-400 text-sm font-semibold uppercase tracking-widest mb-4"
          >
            Smart Surveillance Platform
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="text-5xl font-extrabold text-white leading-tight mb-5"
          >
            See every threat<br />
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              before it happens.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-slate-400 text-lg leading-relaxed mb-8 max-w-md"
          >
            VisionGuard AI watches your cameras, spots threats, and alerts you
            instantly — so you never miss what matters.
          </motion.p>

          <div className="space-y-1">
            {FEATURES.map((f, i) => (
              <FeatureItem key={i} {...f} index={i} />
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="relative z-10 flex items-center gap-12">
          {[
            { value: "99.2%", label: "Detection Rate" },
            { value: "< 0.3s", label: "Alert Speed" },
            { value: "24 / 7", label: "Always Running" },
          ].map(({ value, label }) => (
            <div key={label}>
              <p className="text-3xl font-bold text-white">{value}</p>
              <p className="text-slate-500 text-sm mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[#070d1a] relative overflow-hidden">
        <div className="absolute top-0 left-0 w-80 h-80 bg-blue-600/5 rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-60 h-60 bg-cyan-500/4 rounded-full blur-[80px] pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative z-10 w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-10 lg:hidden">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <p className="text-white font-bold text-xl">VisionGuard AI</p>
          </div>

          <div className="mb-8">
            <h2 className="text-4xl font-bold text-white mb-2">Create your account</h2>
            <p className="text-slate-400 text-lg">Get started — it only takes a minute</p>
          </div>

          <div className="bg-[#0d1829] border border-slate-700/40 rounded-2xl p-8 shadow-2xl">
            <form onSubmit={handleSubmit} className="space-y-5">

              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-3 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl text-sm"
                  >
                    <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Full Name */}
              <div>
                <label className="block text-base font-medium text-slate-300 mb-2">
                  Full name
                </label>
                <div className="relative group">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                  <input
                    type="text"
                    name="fullName"
                    value={formData.fullName}
                    onChange={handleChange}
                    required
                    placeholder="John Doe"
                    className="w-full bg-[#091220] border border-slate-700/50 text-white text-base placeholder:text-slate-600 rounded-xl pl-12 pr-4 py-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-base font-medium text-slate-300 mb-2">
                  Email address
                </label>
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    placeholder="you@example.com"
                    className="w-full bg-[#091220] border border-slate-700/50 text-white text-base placeholder:text-slate-600 rounded-xl pl-12 pr-4 py-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-base font-medium text-slate-300 mb-2">
                  Password
                </label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    placeholder="At least 8 characters"
                    className="w-full bg-[#091220] border border-slate-700/50 text-white text-base placeholder:text-slate-600 rounded-xl pl-12 pr-12 py-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                {formData.password.length > 0 && (
                  <PasswordStrengthBar strength={passwordStrength} />
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-base font-medium text-slate-300 mb-2">
                  Confirm password
                </label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                  <input
                    type={showConfirm ? "text" : "password"}
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                    placeholder="Re-enter your password"
                    className={`w-full bg-[#091220] border text-white text-base placeholder:text-slate-600 rounded-xl pl-12 pr-12 py-4 focus:outline-none transition-all ${
                      passwordsMatch
                        ? "border-emerald-500/60 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/40"
                        : "border-slate-700/50 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                  {passwordsMatch && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.7 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="absolute right-11 top-1/2 -translate-y-1/2"
                    >
                      <CheckCircle className="w-5 h-5 text-emerald-400" />
                    </motion.div>
                  )}
                </div>
              </div>

              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.02 }}
                whileTap={{ scale: loading ? 1 : 0.98 }}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white text-base font-semibold py-4 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-900/50 mt-2"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Creating account...
                  </>
                ) : (
                  <>
                    Create Account
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </motion.button>
            </form>
          </div>

          <p className="text-center text-slate-500 text-base mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
              Sign in
            </Link>
          </p>

          <p className="text-center text-slate-700 text-sm mt-10">
            &copy; 2026 VisionGuard AI. All rights reserved.
          </p>
        </motion.div>
      </div>
    </div>
  );
}

export default Signup;