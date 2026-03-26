import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard, Image, Video, Camera, Users,
  Shield, Settings as SettingsIcon, LogOut, User, Activity
} from "lucide-react";
import authService from "../services/authService";
import { useState, useEffect } from "react";

const menuItems = [
  { path: "/", icon: LayoutDashboard, label: "Dashboard" },
  { path: "/image", icon: Image, label: "Image Analysis" },
  { path: "/video", icon: Video, label: "Video Analysis" },
  { path: "/live", icon: Camera, label: "Live CCTV" },
  { path: "/database", icon: Users, label: "Face Database" },
  { path: "/settings", icon: SettingsIcon, label: "Settings" },
];

export default function Sidebar() {
  const location = useLocation();
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(authService.getCurrentUser());
  }, []);

  const handleLogout = () => {
    if (confirm("Are you sure you want to logout?")) {
      authService.logout();
    }
  };

  return (
    <motion.aside
      initial={{ x: -260 }}
      animate={{ x: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="fixed left-0 top-0 h-screen w-64 flex flex-col bg-[#060c18] border-r border-slate-800/60"
    >
      {/* Logo */}
      <div className="px-6 pt-8 pb-6 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <motion.div
            animate={{
              boxShadow: [
                "0 0 8px rgba(59,130,246,0.25)",
                "0 0 20px rgba(59,130,246,0.55)",
                "0 0 8px rgba(59,130,246,0.25)",
              ],
            }}
            transition={{ duration: 2.5, repeat: Infinity }}
            className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0"
          >
            <Shield className="w-5 h-5 text-white" />
          </motion.div>
          <div>
            <p style={{ fontFamily: "'Dancing Script', cursive", fontSize: '1.2rem', fontWeight: 700 }} className="text-white leading-none">VisionGuard AI</p>
            <p className="text-blue-400 text-xs font-semibold tracking-wider uppercase mt-0.5">
              AI Security
            </p>
          </div>
        </div>
      </div>

      {/* User info */}
      {user && (
        <div className="px-4 py-4 border-b border-slate-800/60">
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-slate-800/40">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">{user.full_name}</p>
              <p className="text-slate-500 text-xs truncate">{user.email}</p>
            </div>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
        {menuItems.map(({ path, icon: Icon, label }) => {
          const isActive = location.pathname === path;
          return (
            <Link key={path} to={path} className="block">
              <motion.div
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.97 }}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                  isActive
                    ? "bg-blue-600/20 border border-blue-500/30 text-blue-400"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="font-medium text-sm">{label}</span>
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 pb-6 pt-4 border-t border-slate-800/60 space-y-3">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors text-sm font-medium"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
        <p className="text-center text-slate-700 text-xs">
          &copy; 2026 VisionGuard AI
        </p>
      </div>
    </motion.aside>
  );
}