/**
 * Converts any browser-recorded audio Blob (WebM, Ogg, etc.) into a
 * 16-bit PCM WAV and returns it as a base64 string ready for the API.
 * AudioContext handles the decoding so this works cross-browser.
 *
 * @param {Blob} blob - raw MediaRecorder output
 * @returns {Promise<string>} base64-encoded WAV
 */
export async function blobToWavBase64(blob) {
  const arrayBuffer = await blob.arrayBuffer()

  // Decode the compressed audio (WebM/Opus, Ogg, etc.) at 16 kHz
  const audioCtx = new AudioContext({ sampleRate: 16000 })
  let audioBuffer
  try {
    audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)
  } finally {
    await audioCtx.close()
  }

  // Mix down to mono
  const rawSamples = audioBuffer.getChannelData(0) // Float32Array, mono or first channel
  const numChannels = audioBuffer.numberOfChannels
  let samples = rawSamples
  if (numChannels > 1) {
    // Average all channels
    samples = new Float32Array(rawSamples.length)
    for (let ch = 0; ch < numChannels; ch++) {
      const chan = audioBuffer.getChannelData(ch)
      for (let i = 0; i < chan.length; i++) samples[i] += chan[i]
    }
    for (let i = 0; i < samples.length; i++) samples[i] /= numChannels
  }

  // Convert Float32 → Int16 PCM
  const pcm = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    pcm[i] = clamped < 0 ? clamped * 32768 : clamped * 32767
  }

  // Build WAV container
  const sampleRate = 16000
  const bitsPerSample = 16
  const dataLen = pcm.buffer.byteLength
  const wavBuf = new ArrayBuffer(44 + dataLen)
  const v = new DataView(wavBuf)
  const str = (off, s) => { for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i)) }

  str(0, 'RIFF')
  v.setUint32(4, 36 + dataLen, true)         // ChunkSize
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true)                  // Subchunk1Size (PCM)
  v.setUint16(20, 1, true)                   // AudioFormat = PCM
  v.setUint16(22, 1, true)                   // NumChannels = 1 (mono)
  v.setUint32(24, sampleRate, true)          // SampleRate
  v.setUint32(28, sampleRate * 2, true)      // ByteRate
  v.setUint16(32, 2, true)                   // BlockAlign
  v.setUint16(34, bitsPerSample, true)       // BitsPerSample
  str(36, 'data')
  v.setUint32(40, dataLen, true)             // Subchunk2Size
  new Int16Array(wavBuf, 44).set(pcm)        // PCM payload

  // Base64 encode
  const bytes = new Uint8Array(wavBuf)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}
