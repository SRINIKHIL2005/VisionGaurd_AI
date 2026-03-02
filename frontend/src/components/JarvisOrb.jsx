import { motion, AnimatePresence } from 'framer-motion'

/**
 * JarvisOrb — Clean Siri-style glass sphere.
 * state: 'idle' | 'listening' | 'thinking' | 'speaking'
 * size:  pixel diameter
 */

const STATE_CONFIG = {
  idle: {
    // Midnight blue — deep, calm, electric
    surface:   'radial-gradient(circle at 36% 28%, #93c5fd 0%, #3b82f6 22%, #1d4ed8 50%, #1e3a8a 75%, #0f172a 100%)',
    innerGlow: 'radial-gradient(circle at 50% 45%, rgba(59,130,246,0.30) 0%, transparent 70%)',
    glowColor: '#2563eb',
    glowRgba:  'rgba(37,99,235,0.55)',
    ringRgba:  'rgba(96,165,250,0.50)',
    rings:     0,
  },
  listening: {
    // Vivid cyan-aqua — alive and receptive
    surface:   'radial-gradient(circle at 36% 28%, #6ee7b7 0%, #10b981 22%, #059669 50%, #065f46 75%, #022c22 100%)',
    innerGlow: 'radial-gradient(circle at 50% 45%, rgba(16,185,129,0.30) 0%, transparent 70%)',
    glowColor: '#10b981',
    glowRgba:  'rgba(16,185,129,0.65)',
    ringRgba:  'rgba(52,211,153,0.55)',
    rings:     3,
  },
  thinking: {
    // Rose-magenta — signals active cognition
    surface:   'radial-gradient(circle at 36% 28%, #fda4af 0%, #f43f5e 22%, #e11d48 50%, #9f1239 75%, #4c0519 100%)',
    innerGlow: 'radial-gradient(circle at 50% 45%, rgba(244,63,94,0.28) 0%, transparent 70%)',
    glowColor: '#e11d48',
    glowRgba:  'rgba(225,29,72,0.58)',
    ringRgba:  'rgba(251,113,133,0.45)',
    rings:     1,
  },
  speaking: {
    // Sky blue — bright, confident output
    surface:   'radial-gradient(circle at 36% 28%, #bae6fd 0%, #38bdf8 22%, #0284c7 50%, #075985 75%, #082f49 100%)',
    innerGlow: 'radial-gradient(circle at 50% 45%, rgba(56,189,248,0.28) 0%, transparent 70%)',
    glowColor: '#0284c7',
    glowRgba:  'rgba(2,132,199,0.65)',
    ringRgba:  'rgba(56,189,248,0.55)',
    rings:     2,
  },
}

const ORB_SCALE = {
  idle:      { scale: [1, 1.028, 1],                          transition: { duration: 3.8, repeat: Infinity, ease: 'easeInOut' } },
  listening: { scale: [1, 1.10, 0.96, 1.07, 1],              transition: { duration: 1.2, repeat: Infinity, ease: 'easeInOut' } },
  thinking:  { scale: [1, 1.05, 0.97, 1.04, 1],              transition: { duration: 0.95, repeat: Infinity, ease: 'easeInOut' } },
  speaking:  { scale: [1, 1.18, 0.91, 1.14, 0.94, 1.07, 1],  transition: { duration: 0.55, repeat: Infinity, ease: 'easeInOut' } },
}

const GLOW_PULSE = {
  idle:      { opacity: [0.50, 0.70, 0.50],            transition: { duration: 3.8, repeat: Infinity } },
  listening: { opacity: [0.60, 0.95, 0.60],            transition: { duration: 1.1, repeat: Infinity } },
  thinking:  { opacity: [0.52, 0.85, 0.52],            transition: { duration: 0.90, repeat: Infinity } },
  speaking:  { opacity: [0.65, 1.00, 0.55, 0.90, 0.65], transition: { duration: 0.55, repeat: Infinity } },
}

export default function JarvisOrb({ state = 'idle', size = 180 }) {
  const cfg  = STATE_CONFIG[state] || STATE_CONFIG.idle
  const half = size / 2

  /* glow layers – perfectly centred with inset-0 flex  */
  const GlowLayer = ({ radius, blur, opacity }) => (
    <motion.div
      className="absolute inset-0 flex items-center justify-center pointer-events-none"
      animate={GLOW_PULSE[state]}
      style={{ opacity }}
    >
      <div
        className="rounded-full"
        style={{
          width:  size * radius,
          height: size * radius,
          background:  cfg.glowRgba,
          filter: `blur(${size * blur}px)`,
        }}
      />
    </motion.div>
  )

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: size, height: size }}
    >
      {/* ── Ambient bloom (far, very blurry) ─────────────── */}
      <GlowLayer radius={1.80} blur={0.55} opacity={0.38} />
      {/* ── Near halo ─────────────────────────────────────── */}
      <GlowLayer radius={1.10} blur={0.22} opacity={0.65} />

      {/* ── Ripple rings (listening / speaking) ───────────── */}
      <AnimatePresence>
        {Array.from({ length: cfg.rings }).map((_, i) => (
          <motion.div
            key={`${state}-ring-${i}-${size}`}
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
          >
            <motion.div
              className="rounded-full"
              style={{
                width:  size, height: size,
                border: `${i === 0 ? 2 : 1.5}px solid ${cfg.ringRgba}`,
              }}
              initial={{ scale: 1, opacity: 0.75 }}
              animate={{ scale: 2.5 + i * 0.4, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.9, repeat: Infinity, delay: i * 0.55, ease: 'easeOut' }}
            />
          </motion.div>
        ))}
      </AnimatePresence>

      {/* ── Thinking: spinning highlight arc ──────────────── */}
      {state === 'thinking' && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <motion.div
            className="rounded-full"
            style={{
              width:  size + 8, height: size + 8,
              background: `conic-gradient(from 0deg, transparent 60%, ${cfg.glowRgba} 78%, rgba(255,255,255,0.75) 85%, ${cfg.glowRgba} 92%, transparent 100%)`,
            }}
            animate={{ rotate: 360 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          />
        </div>
      )}

      {/* ══════════ Glass sphere ══════════════════════════════ */}
      <motion.div
        className="relative rounded-full overflow-hidden"
        style={{
          width:  size, height: size,
          background: cfg.surface,
          boxShadow: [
            `0 0 ${half * 0.55}px ${cfg.glowRgba}`,
            `0 0 ${half * 0.18}px ${cfg.glowRgba}`,
            `inset 0 2px ${half * 0.18}px rgba(255,255,255,0.18)`,
            `inset 0 -2px ${half * 0.14}px rgba(0,0,0,0.40)`,
          ].join(', '),
          willChange: 'transform',
          flexShrink: 0,
        }}
        animate={ORB_SCALE[state]}
      >
        {/* subsurface scatter */}
        <div className="absolute inset-0 rounded-full" style={{ background: cfg.innerGlow }} />

        {/* primary large diffuse highlight — top-left */}
        <div
          className="absolute rounded-full"
          style={{
            width:  size * 0.62, height: size * 0.58,
            top:    size * 0.02, left: size * 0.04,
            background: 'radial-gradient(ellipse at 40% 35%, rgba(255,255,255,0.32) 0%, rgba(255,255,255,0.10) 50%, transparent 100%)',
            filter: `blur(${size * 0.08}px)`,
          }}
        />

        {/* sharp specular pinpoint */}
        <div
          className="absolute rounded-full"
          style={{
            width:  size * 0.22, height: size * 0.22,
            top:    size * 0.09, left: size * 0.17,
            background: 'radial-gradient(circle, rgba(255,255,255,0.96) 0%, rgba(255,255,255,0.50) 45%, transparent 100%)',
            filter: `blur(${size * 0.012}px)`,
          }}
        />

        {/* secondary soft specular (right angle) */}
        <div
          className="absolute rounded-full"
          style={{
            width:  size * 0.11, height: size * 0.11,
            top:    size * 0.30, right: size * 0.18,
            background: 'radial-gradient(circle, rgba(255,255,255,0.50) 0%, transparent 100%)',
            filter: `blur(${size * 0.022}px)`,
          }}
        />

        {/* bottom rim backlight */}
        <div
          className="absolute"
          style={{
            width:  size * 0.70, height: size * 0.14,
            bottom: size * 0.05, left: '50%',
            transform: 'translateX(-50%)',
            background: `radial-gradient(ellipse, ${cfg.glowRgba} 0%, transparent 80%)`,
            filter: `blur(${size * 0.05}px)`,
          }}
        />

        {/* deep vignette for sphere depth */}
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: 'radial-gradient(circle at 62% 65%, rgba(0,0,0,0.42) 0%, transparent 58%)' }}
        />

        {/* ── Speaking: waveform bars ─────────────────────── */}
        {state === 'speaking' && (
          <div
            className="absolute inset-0 flex items-end justify-center pb-[24%]"
            style={{ gap: Math.max(2, size * 0.018) }}
          >
            {[0.48, 0.80, 0.96, 0.64, 1, 0.72, 0.94, 0.60, 0.84, 0.50, 0.76].map((h, i) => (
              <motion.div
                key={i}
                className="rounded-full"
                style={{
                  width:  Math.max(2, size * 0.014),
                  height: size * 0.38 * h,
                  background: 'rgba(255,255,255,0.78)',
                  flexShrink: 0,
                }}
                animate={{ scaleY: [1, 0.28 + (i % 3) * 0.20, 0.72, 1] }}
                transition={{ duration: 0.36 + i * 0.038, repeat: Infinity, delay: i * 0.048, ease: 'easeInOut' }}
              />
            ))}
          </div>
        )}

        {/* ── Listening: aurora swirl ─────────────────────── */}
        {state === 'listening' && (
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{
              background: `conic-gradient(from 0deg, transparent 25%, ${cfg.ringRgba} 50%, rgba(255,255,255,0.20) 62%, transparent 78%)`,
              opacity: 0.45,
            }}
            animate={{ rotate: 360 }}
            transition={{ duration: 2.8, repeat: Infinity, ease: 'linear' }}
          />
        )}
      </motion.div>
    </div>
  )
}
