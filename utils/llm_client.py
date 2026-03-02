"""
LLM Client â€” Gemini interface for VisionGuard AI Assistant

Sends structured security-context prompts to Gemini and returns
concise, natural-language responses for the Jarvis voice assistant.
When a live camera frame is available, it is sent as an image part so
Gemini can SEE the actual scene rather than relying only on text metadata.
"""

from __future__ import annotations

import base64
from typing import List, Optional


class GeminiClient:
    """Wraps google-genai to generate Jarvis-style security responses."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai is not installed. "
                "Run: pip install google-genai"
            )

        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name
        self._genai = genai
        print(f"âœ… GeminiClient ready (model={model_name})")

    # ------------------------------------------------------------------ #

    def generate(
        self,
        assistant_name: str,
        camera_summary: str,
        user_query: str,
        retrieved_logs: List[str],
        ui_context: str = "",
        frame_base64: Optional[str] = None,
    ) -> str:
        """
        Build a security-context prompt and call Gemini.

        Parameters
        ----------
        assistant_name : str
            The assistant's configured name (e.g. 'Jarvis').
        camera_summary : str
            Plain-text summary of the current camera analysis result.
        user_query : str
            What the user just said.
        retrieved_logs : list[str]
            Top-k detection history entries retrieved from FAISS.
        ui_context : str
            Current web interface state (page, live status, actions).
        frame_base64 : str, optional
            Base-64 JPEG of the annotated live camera frame. When provided,
            Gemini receives the actual image and can make a real visual judgment
            about whether something is actually dangerous or harmless.
        """
        log_block = (
            "\n".join(f"  - {log}" for log in retrieved_logs)
            if retrieved_logs
            else "  No recent detection records available."
        )

        has_image = bool(frame_base64)
        image_note = (
            "You are also being shown the actual annotated camera frame (image attached). "
            "Use the image as your PRIMARY source of truth â€” if the detectors flagged a high "
            "risk score but the image looks like a normal everyday scene (people walking, sitting, "
            "working etc.), say so honestly. Override the metadata with what you actually SEE."
        ) if has_image else (
            "No live frame is attached â€” rely on the structured detection data below."
        )

        prompt = f"""You are {assistant_name}, an AI security surveillance assistant modelled after \
J.A.R.V.I.S. from Iron Man â€” sharp, calm, observant, and conversational. You watch live camera feeds \
and describe what is happening in plain human language. You are also a trained threat analyst.

{image_note}

Here is the structured detection data from the current camera frame:
{camera_summary}

Recent surveillance log history:
{log_block}

User said: "{user_query}"

{f'Web interface context (what the user sees / what you are doing):\n{ui_context}' if ui_context else ''}

Instructions â€” follow ALL of these:

1. HUMAN LANGUAGE: Talk like a sharp human observer, never like a data readout.
   - Instead of "3 persons detected, risk LOW" say "Three people in frame â€” nothing alarming."
   - Infer activity from objects (sports ball/bat â†’ playing cricket or baseball; laptop â†’ working; \
bicycle â†’ cycling; TV/chair â†’ watching something; books â†’ studying; phone â†’ on a call).

2. IMAGE PRIORITY (when image is attached): The actual camera frame is the ground truth.
   - If the image shows a normal, harmless scene, describe it as such â€” do NOT report HIGH risk \
just because a detector scored it high. Detectors can be wrong.
   - If the image shows something genuinely alarming, flag it urgently.
   - Describe what you actually SEE (postures, activities, context) not just what metadata says.

3. WEAPON SCENARIOS â€” be very specific and urgent:
   - If a WEAPON ALERT is in the data AND visible in the image, name the exact weapon type.
   - Example: "Alert â€” Person 2 appears to be holding a pistol. Treat this as a live threat."
   - If the image shows no weapon despite the alert, say "The detector flagged a potential weapon \
but the image looks clear â€” keeping an eye on it."

4. ACCIDENTS / DISTRESS SCENARIOS:
   - If ACCIDENT/DISTRESS INDICATORS are in the data (fire, smoke, blood, crash, fall, explosion), \
describe it urgently: "There's smoke visible in the feed â€” possible fire, recommend immediate check."

5. QUERY TYPE â€” decide which applies:
   (A) STATUS / SCENE query â†’ describe scene naturally, lead with threats if real.
   (B) GENERAL query â†’ answer directly, skip camera data unless needed.

6. CAMERA OFF RULE: If camera summary says "Live CCTV is currently OFF", do NOT describe any scene. \
You have zero visual data. Say "The camera isn't running right now."

7. ALWAYS INTERRUPT FOR THREATS: If a weapon or deepfake is confirmed in image/data, flag it first.

8. LENGTH: 1â€“2 sentences only. No bullet points, no markdown, plain speech.
9. TONE: Calm, confident, direct â€” like a seasoned analyst talking to a colleague.
10. WEB CONTROL QUERIES: Confirm navigation actions naturally ("Taking you to Live CCTV now, sir."). \
If Web Control is DISABLED and user asks to control UI, suggest enabling it in Settings.
"""

        try:
            if has_image:
                # Multimodal request â€” send image + text so Gemini can actually SEE the scene
                try:
                    image_bytes = base64.b64decode(frame_base64)
                    image_part = self._genai.types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg",
                    )
                    response = self._client.models.generate_content(
                        model=self._model_name,
                        contents=[image_part, prompt],
                    )
                except Exception as img_err:
                    print(f"[Gemini] Multimodal failed, falling back to text-only: {img_err}")
                    response = self._client.models.generate_content(
                        model=self._model_name,
                        contents=prompt,
                    )
            else:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                )

            text = (response.text or "").strip()
            # Safety: if response is empty or blocked, fall back gracefully
            if not text:
                return f"I'm monitoring the situation. {camera_summary}"
            return text
        except Exception as e:
            print(f"[Gemini] generate_content failed: {e}")
            return f"I'm monitoring the situation. {camera_summary}"

