"""
Telegram Bot Notifier for Unknown Face Detection
Sends notifications to owner with photos and interactive approval buttons
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from io import BytesIO
import cv2
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
try:
    from telegram.request import HTTPXRequest
except Exception:  # pragma: no cover
    HTTPXRequest = None
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import logging

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_NAME = 1
WAITING_FOR_REJECT_ACTION = 2
WAITING_FOR_TEMP_NAME = 3

class TelegramNotifier:
    """Handles Telegram notifications for unknown face detections"""
    
    def __init__(self, bot_token: str, owner_chat_id: int, config: dict, face_recognizer=None):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot API token
            owner_chat_id: Owner's Telegram chat ID
            config: Configuration dictionary with settings
            face_recognizer: Shared FaceRecognizer instance from pipeline (to avoid sync issues)
        """
        self.bot_token = bot_token
        self.owner_chat_id = owner_chat_id
        self.config = config
        self.face_recognizer = face_recognizer  # Use shared instance
        self.app = None
        self.pending_approvals = {}  # {detection_id: {data}}
        self.conversation_state = {}  # {chat_id: {state, detection_id}}

        # Rate limiting: enforce minimum time between notifications
        self._last_notification_at: Optional[datetime] = None
        self._send_lock = asyncio.Lock()
        self._last_skip_reason: Optional[str] = None

        # Track lifecycle
        self._started: bool = False
        self._direct_bot: Optional[Bot] = None
        
        # Paths
        self.unknown_queue_path = Path("data/face_database/unknown_queue.json")
        self.unknown_images_dir = Path("data/face_database/unknown_images")
        self.unknown_images_dir.mkdir(parents=True, exist_ok=True)
        
        # Settings from config
        self.cooldown_minutes = config.get("cooldown_minutes", 3)
        self.retention_days = config.get("retention_days", 10)
        
        logger.info("✅ Telegram Notifier initialized")
    
    async def initialize(self):
        """Initialize the Telegram bot application"""
        try:
            if self._started:
                return

            # Under heavy CPU load (live CCTV), Telegram requests can be delayed.
            # Use more forgiving timeouts to reduce spurious "Timed out" failures.
            if HTTPXRequest is not None:
                request = HTTPXRequest(connect_timeout=20.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=20.0)
                self.app = Application.builder().token(self.bot_token).request(request).build()
            else:
                self.app = Application.builder().token(self.bot_token).build()
            
            # Add handlers
            self.app.add_handler(CommandHandler("start", self._handle_start))
            self.app.add_handler(CallbackQueryHandler(self._handle_callback))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
            
            # Start bot (non-blocking)
            await self.app.initialize()
            await self.app.start()

            # Start polling to receive updates (button clicks, messages).
            # If polling fails (network hiccup), keep notifier usable for outbound alerts.
            try:
                if self.app.updater:
                    await self.app.updater.start_polling(drop_pending_updates=True)
                    logger.info("✅ Telegram bot polling for updates (buttons will work)")
            except Exception as poll_err:
                logger.warning(f"⚠️ Telegram polling start failed, continuing in send-only mode: {poll_err}")

            logger.info("✅ Telegram bot started successfully")

            # Startup message should never abort notifier initialization.
            try:
                await self.send_startup_message()
            except Exception as startup_err:
                logger.warning(f"⚠️ Telegram startup message skipped: {startup_err}")

            self._started = True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram bot: {e}")
            # Do not raise here; send_text_message/send_photo_message can still
            # work through direct-bot fallback even if polling/app startup fails.
            self._started = False

    def _get_direct_bot(self) -> Bot:
        """Get or create a lightweight Bot client for outbound sends."""
        if self._direct_bot is not None:
            return self._direct_bot

        if HTTPXRequest is not None:
            request = HTTPXRequest(connect_timeout=25.0, read_timeout=35.0, write_timeout=35.0, pool_timeout=25.0)
            self._direct_bot = Bot(token=self.bot_token, request=request)
        else:
            self._direct_bot = Bot(token=self.bot_token)
        return self._direct_bot
    
    async def shutdown(self):
        """Shutdown the Telegram bot gracefully"""
        if self.app:
            # Stop polling first
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            
            await self.app.stop()
            await self.app.shutdown()
        self._started = False


    async def send_text_message(self, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a plain Telegram message to the owner chat."""
        try:
            bot = self.app.bot if self.app else self._get_direct_bot()
            await bot.send_message(
                chat_id=self.owner_chat_id,
                text=text,
                parse_mode=parse_mode,
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send text message: {e}")
            return False

    async def send_photo_message(
        self,
        image_bytes: bytes,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
    ) -> bool:
        """Send a photo message to the owner chat from raw bytes."""
        try:
            if not image_bytes:
                return False

            bot = self.app.bot if self.app else self._get_direct_bot()

            # Re-encode to a moderate JPEG size for Telegram reliability.
            # Large raw images can time out during upload on slower links.
            payload = image_bytes
            try:
                np_buf = np.frombuffer(image_bytes, dtype=np.uint8)
                img = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    max_side = max(h, w)
                    if max_side > 1280:
                        scale = 1280.0 / float(max_side)
                        new_w = max(1, int(w * scale))
                        new_h = max(1, int(h * scale))
                        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                    ok, enc = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ok:
                        payload = enc.tobytes()
            except Exception:
                # Fall back to original bytes if re-encode fails.
                pass

            # Retry a few times because Telegram network calls can be transient.
            for attempt in range(1, 4):
                try:
                    stream = BytesIO(payload)
                    stream.name = "alert.jpg"
                    stream.seek(0)

                    await bot.send_photo(
                        chat_id=self.owner_chat_id,
                        photo=stream,
                        caption=caption,
                        parse_mode=parse_mode,
                    )
                    return True
                except Exception as send_err:
                    logger.warning(f"⚠️ Photo send attempt {attempt}/3 failed: {send_err}")
                    if attempt < 3:
                        await asyncio.sleep(0.8)

            return False
        except Exception as e:
            logger.error(f"❌ Failed to send photo message: {e}")
            return False
    
    async def send_startup_message(self):
        """Send a test message when bot starts"""
        try:
            message = (
                "🤖 *VRSU Security System Online*\n\n"
                "✅ Face recognition active\n"
                "✅ Unknown face detection enabled\n"
                "✅ Notifications ready\n\n"
                "You will receive alerts when unknown persons are detected."
            )
            bot = self.app.bot if self.app else self._get_direct_bot()
            await bot.send_message(
                chat_id=self.owner_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("📤 Startup message sent to owner")
        except Exception as e:
            logger.error(f"❌ Failed to send startup message: {e}")
    
    def _load_queue(self) -> List[Dict]:
        """Load unknown faces queue from JSON"""
        if self.unknown_queue_path.exists():
            with open(self.unknown_queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_queue(self, queue: List[Dict]):
        """Save unknown faces queue to JSON"""
        self.unknown_queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.unknown_queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    
    def check_cooldown(self, face_embedding: np.ndarray) -> bool:
        """
        Check if this face was recently notified (within cooldown period)
        
        Args:
            face_embedding: Face embedding to check
            
        Returns:
            True if can notify (not in cooldown), False otherwise
        """
        queue = self._load_queue()
        cooldown_threshold = datetime.now() - timedelta(minutes=self.cooldown_minutes)
        
        for detection in queue:
            if detection.get('status') == 'notified':
                detection_time = datetime.fromisoformat(detection['timestamp'])
                
                # Check if within cooldown period
                if detection_time > cooldown_threshold:
                    # Compare embeddings (cosine similarity)
                    stored_embeddings = [np.array(emb) for emb in detection.get('embeddings', [])]
                    for stored_emb in stored_embeddings:
                        similarity = np.dot(face_embedding, stored_emb) / (
                            np.linalg.norm(face_embedding) * np.linalg.norm(stored_emb)
                        )
                        if similarity > 0.85:  # Same person threshold
                            logger.info(f"⏳ Face in cooldown period ({self.cooldown_minutes}min)")
                            return False
        
        return True
    
    def cleanup_old_detections(self):
        """Remove detections older than retention_days"""
        queue = self._load_queue()
        retention_threshold = datetime.now() - timedelta(days=self.retention_days)
        
        new_queue = []
        cleaned_count = 0
        
        for detection in queue:
            detection_time = datetime.fromisoformat(detection['timestamp'])
            
            if detection_time > retention_threshold:
                new_queue.append(detection)
            else:
                # Delete associated image file
                image_path = Path(detection.get('image_path', ''))
                if image_path.exists():
                    image_path.unlink()
                cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_queue(new_queue)
            logger.info(f"🧹 Cleaned up {cleaned_count} old detections (>{self.retention_days} days)")
    
    def create_annotated_image(
        self, 
        image: np.ndarray, 
        bounding_boxes: List[Tuple[int, int, int, int]],
        unknown_indices: List[int]
    ) -> np.ndarray:
        """
        Draw rectangles around unknown faces
        
        Args:
            image: Original image
            bounding_boxes: List of (x, y, w, h) for all faces
            unknown_indices: Indices of unknown faces to highlight
            
        Returns:
            Annotated image with rectangles
        """
        annotated = image.copy()
        
        for idx, (x, y, w, h) in enumerate(bounding_boxes):
            if idx in unknown_indices:
                # Red rectangle for unknown faces
                cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 255), 3)
                
                # Add number label
                label = f"#{idx+1}"
                cv2.putText(
                    annotated, label, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2
                )
        
        return annotated
    
    async def send_unknown_face_notification(
        self,
        image: np.ndarray,
        unknown_faces: List[Dict],  # [{"embedding": array, "bbox": (x,y,w,h)}]
        camera_location: str = "Unknown",
        risk_assessment: Optional[Dict] = None,
        summary: Optional[str] = None,
        suspicious_objects: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send notification about unknown face(s) detected
        
        Args:
            image: Original frame image
            unknown_faces: List of unknown face data with embeddings and bboxes
            camera_location: Location identifier for the camera
            
        Returns:
            Detection ID if successful, None otherwise
        """
        try:
            # Serialize the entire send path.
            # Without this, multiple concurrent tasks can pass the rate-limit check
            # before `_last_notification_at` gets updated, causing floods/timeouts.
            async with self._send_lock:
                if self._last_notification_at is not None:
                    seconds_since_last = (datetime.now() - self._last_notification_at).total_seconds()
                    if seconds_since_last < 20:
                        self._last_skip_reason = "rate_limit"
                        logger.info(f"⏱️ Skipping Telegram notification (rate limit: {seconds_since_last:.1f}s since last < 20s)")
                        return None

                # Generate unique detection ID
                detection_id = f"uf_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

                # Create annotated image with rectangles (OpenCV work off the event loop)
                bounding_boxes = [face['bbox'] for face in unknown_faces]
                unknown_indices = list(range(len(unknown_faces)))
                annotated_image = await asyncio.to_thread(
                    self.create_annotated_image,
                    image,
                    bounding_boxes,
                    unknown_indices,
                )

                # Save annotated image (disk IO off the event loop)
                image_filename = f"{detection_id}.jpg"
                image_path = self.unknown_images_dir / image_filename
                await asyncio.to_thread(cv2.imwrite, str(image_path), annotated_image)

                # Save to queue
                detection_data = {
                    "id": detection_id,
                    "timestamp": datetime.now().isoformat(),
                    "image_path": str(image_path),
                    "embeddings": [face['embedding'].tolist() for face in unknown_faces],
                    "bounding_boxes": bounding_boxes,
                    "camera_location": camera_location,
                    "status": "notified",
                    "unknown_count": len(unknown_faces)
                }

                queue = self._load_queue()
                queue.append(detection_data)
                self._save_queue(queue)

                # Prepare message
                timestamp_str = datetime.now().strftime("%b %d, %Y - %H:%M:%S")
                face_count = len(unknown_faces)
            
            if face_count == 1:
                caption = (
                    "🚨 *Unknown Person Detected*\n\n"
                    f"📍 Location: {camera_location}\n"
                    f"🕐 Time: {timestamp_str}\n"
                    f"👥 Unknown Faces: {face_count}\n\n"
                    "Click Approve to add this person to known faces."
                )
            else:
                caption = (
                    f"🚨 *Multiple Unknown Persons Detected*\n\n"
                    f"📍 Location: {camera_location}\n"
                    f"🕐 Time: {timestamp_str}\n"
                    f"👥 Unknown Faces: {face_count}\n\n"
                    f"⚠️ {face_count} unknown persons in frame\n"
                    "Click Approve to add ALL faces to database."
                )

            # Add risk + summary if provided
            if risk_assessment:
                risk_level = risk_assessment.get("risk_level") or risk_assessment.get("level")
                risk_score = risk_assessment.get("risk_score")
                if risk_level is not None:
                    caption += f"\n\n⚠️ *Risk Level:* {risk_level}"
                if risk_score is not None:
                    caption += f"\n📊 *Risk Score:* {risk_score}"

            if summary:
                caption += f"\n\n📝 *Summary:* {summary}"

            if suspicious_objects:
                caption += f"\n\n🚫 *Suspicious Objects:* {', '.join(suspicious_objects)}"
            
            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve & Add", callback_data=f"approve_{detection_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{detection_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send photo with buttons
            with open(image_path, 'rb') as photo:
                await self.app.bot.send_photo(
                    chat_id=self.owner_chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )

            # Record send time
            self._last_notification_at = datetime.now()
            self._last_skip_reason = None

            # Store in pending approvals
            self.pending_approvals[detection_id] = detection_data

            logger.info(f"📤 Notification sent for detection {detection_id} ({face_count} unknown faces)")
            return detection_id
            
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
            return None
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "👋 Welcome to VRSU Security System!\n\n"
            "I will notify you when unknown persons are detected.\n"
            "Use the buttons in notifications to approve or reject faces."
        )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks (Approve/Reject)"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        action, detection_id = callback_data.split('_', 1)
        
        if action == "approve":
            # Store detection ID for conversation
            self.conversation_state[query.message.chat_id] = {
                "state": WAITING_FOR_NAME,
                "detection_id": detection_id,
                "face_count": self.pending_approvals.get(detection_id, {}).get("unknown_count", 1)
            }
            
            face_count = self.conversation_state[query.message.chat_id]["face_count"]
            
            if face_count == 1:
                prompt = "✅ *Approval Started*\n\nPlease enter the person's name:"
            else:
                prompt = (
                    f"✅ *Approval Started*\n\n"
                    f"⚠️ {face_count} faces will be added with the same name.\n"
                    f"Please enter the name for all persons:"
                )
            
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n⏳ *Waiting for name...*",
                parse_mode='Markdown'
            )
            await query.message.reply_text(prompt, parse_mode='Markdown')
            
        elif action == "reject":
            # Show rejection options instead of just dismissing
            self.conversation_state[query.message.chat_id] = {
                "state": WAITING_FOR_REJECT_ACTION,
                "detection_id": detection_id
            }
            
            # Create follow-up options
            reject_keyboard = [
                [InlineKeyboardButton("🚨 EMERGENCY - Send Alarm", callback_data=f"emergency_{detection_id}")],
                [InlineKeyboardButton("👷 Temporary Access (Painter/Worker)", callback_data=f"temporary_{detection_id}")],
                [InlineKeyboardButton("✅ Just Ignore - No Threat", callback_data=f"ignore_{detection_id}")]
            ]
            reject_markup = InlineKeyboardMarkup(reject_keyboard)
            
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n❓ *What action should we take?*",
                parse_mode='Markdown'
            )
            await query.message.reply_text(
                "🤔 *You rejected adding to database.*\n\n"
                "Please choose an action:\n\n"
                "🚨 **EMERGENCY** - Intruder/Threat (triggers alarm)\n"
                "👷 **Temporary Access** - Worker/Visitor (short-term database)\n"
                "✅ **Just Ignore** - No threat, dismiss",
                parse_mode='Markdown',
                reply_markup=reject_markup
            )
            
        elif action == "emergency":
            # EMERGENCY - Send alarm
            await self._handle_emergency(detection_id, query)
            
        elif action == "temporary":
            # Temporary access - ask for name
            self.conversation_state[query.message.chat_id] = {
                "state": WAITING_FOR_TEMP_NAME,
                "detection_id": detection_id,
                "face_count": self.pending_approvals.get(detection_id, {}).get("unknown_count", 1)
            }
            
            await query.edit_message_text(
                "👷 *Temporary Access*\n\n"
                "Please enter name/role:\n"
                "(e.g., 'Painter John', 'Delivery Person', 'Contractor')",
                parse_mode='Markdown'
            )
            
        elif action == "ignore":
            # Just ignore - mark as dismissed
            if detection_id in self.pending_approvals:
                del self.pending_approvals[detection_id]
            
            queue = self._load_queue()
            for detection in queue:
                if detection['id'] == detection_id:
                    detection['status'] = 'ignored'
                    detection['action'] = 'no_threat'
                    break
            self._save_queue(queue)
            
            await query.edit_message_text(
                "✅ *Dismissed*\n\n"
                "Detection ignored. No action taken.",
                parse_mode='Markdown'
            )
            
            # Clear conversation state
            if query.message.chat_id in self.conversation_state:
                del self.conversation_state[query.message.chat_id]
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (name input during approval)"""
        chat_id = update.message.chat_id
        
        # Check if in conversation state
        if chat_id not in self.conversation_state:
            return
        
        state_data = self.conversation_state[chat_id]
        
        if state_data["state"] == WAITING_FOR_NAME:
            # Permanent database addition
            person_name = update.message.text.strip()
            detection_id = state_data["detection_id"]
            
            if not person_name:
                await update.message.reply_text("⚠️ Please enter a valid name.")
                return
            
            # Extract Telegram user info
            telegram_user_info = {
                'user_id': update.message.from_user.id,
                'username': update.message.from_user.username,
                'first_name': update.message.from_user.first_name,
                'last_name': update.message.from_user.last_name
            }
            
            # Call the approval function (will be implemented in API)
            success = await self._add_to_known_faces(detection_id, person_name, category="permanent", telegram_user_info=telegram_user_info)
            
            if success:
                face_count = state_data["face_count"]
                await update.message.reply_text(
                    f"✅ *Success!*\n\n"
                    f"Added {face_count} face(s) as: *{person_name}*\n"
                    f"📁 Category: Permanent Database\n"
                    f"This person will now be recognized.",
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Detection {detection_id} approved as '{person_name}' (permanent)")
            else:
                await update.message.reply_text(
                    "❌ Failed to add faces. Please try again or contact support."
                )
            
            # Clear conversation state
            del self.conversation_state[chat_id]
            if detection_id in self.pending_approvals:
                del self.pending_approvals[detection_id]
        
        elif state_data["state"] == WAITING_FOR_TEMP_NAME:
            # Temporary database addition
            person_name = update.message.text.strip()
            detection_id = state_data["detection_id"]
            
            if not person_name:
                await update.message.reply_text("⚠️ Please enter a valid name/role.")
                return
            
            # Extract Telegram user info
            telegram_user_info = {
                'user_id': update.message.from_user.id,
                'username': update.message.from_user.username,
                'first_name': update.message.from_user.first_name,
                'last_name': update.message.from_user.last_name
            }
            
            # Add to temporary database
            success = await self._add_to_known_faces(detection_id, f"TEMP_{person_name}", category="temporary", telegram_user_info=telegram_user_info)
            
            if success:
                face_count = state_data["face_count"]
                await update.message.reply_text(
                    f"✅ *Temporary Access Granted*\n\n"
                    f"Added {face_count} face(s) as: *{person_name}*\n"
                    f"📁 Category: Temporary (Worker/Visitor)\n"
                    f"⏰ Auto-expires: 24 hours\n\n"
                    f"This person will be recognized temporarily.",
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Detection {detection_id} added as temporary '{person_name}'")
            else:
                await update.message.reply_text(
                    "❌ Failed to add temporary access. Please try again."
                )
            
            # Clear conversation state
            del self.conversation_state[chat_id]
            if detection_id in self.pending_approvals:
                del self.pending_approvals[detection_id]
    
    async def _add_to_known_faces(self, detection_id: str, person_name: str, category: str = "permanent", telegram_user_info: dict = None) -> bool:
        """
        Add unknown faces to known database
        
        Args:
            detection_id: Detection ID from queue
            person_name: Name to assign to the face(s)
            category: "permanent" or "temporary"
            telegram_user_info: Dict with Telegram user metadata (user_id, username, first_name, last_name)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load queue
            queue = self._load_queue()
            detection_data = None
            
            for detection in queue:
                if detection['id'] == detection_id:
                    detection_data = detection
                    break
            
            if not detection_data:
                logger.error(f"Detection {detection_id} not found in queue")
                return False
            
            # Use shared face recognizer instance (passed during init)
            if not self.face_recognizer:
                logger.error("Face recognizer not available")
                return False
            
            # Add each embedding as the same person
            embeddings = [np.array(emb) for emb in detection_data['embeddings']]
            
            # Prepare metadata with Telegram user info
            from datetime import datetime
            
            # Build approver info string
            if telegram_user_info:
                approver_parts = []
                if telegram_user_info.get('first_name') or telegram_user_info.get('last_name'):
                    full_name = f"{telegram_user_info.get('first_name', '')} {telegram_user_info.get('last_name', '')}".strip()
                    approver_parts.append(full_name)
                if telegram_user_info.get('username'):
                    approver_parts.append(f"@{telegram_user_info['username']}")
                approver_parts.append(f"ID:{telegram_user_info['user_id']}")
                approver_info = " | ".join(approver_parts)
            else:
                approver_info = f"Chat ID: {self.owner_chat_id}"
            
            metadata = {
                'added_date': datetime.now().isoformat(),
                'photo_path': detection_data.get('image_path'),
                'approved_by': approver_info,
                'camera_location': detection_data.get('camera_location', 'Unknown'),
                'telegram_user_id': telegram_user_info.get('user_id') if telegram_user_info else None,
                'telegram_username': telegram_user_info.get('username') if telegram_user_info else None,
                'telegram_first_name': telegram_user_info.get('first_name') if telegram_user_info else None,
                'telegram_last_name': telegram_user_info.get('last_name') if telegram_user_info else None,
                'approval_timestamp': datetime.now().isoformat()
            }
            
            for idx, embedding in enumerate(embeddings):
                # For multiple faces, add suffix if needed
                if len(embeddings) > 1:
                    name = f"{person_name}_{idx+1}"
                else:
                    name = person_name
                
                # Add to database with metadata
                self.face_recognizer.add_face(name, embedding, metadata)
            
            logger.info(f"✅ Added {len(embeddings)} face(s) as '{person_name}' with metadata (now has {len(self.face_recognizer.face_database)} identities)")
            
            # Update queue status
            detection_data['status'] = 'approved'
            detection_data['approved_name'] = person_name
            detection_data['category'] = category
            detection_data['approval_time'] = datetime.now().isoformat()
            self._save_queue(queue)
            
            logger.info(f"✅ Added {len(embeddings)} face(s) as '{person_name}' ({category})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add faces to database: {e}")
            return False
    
    async def _handle_emergency(self, detection_id: str, query):
        """Handle emergency/intruder alert"""
        try:
            # Mark as emergency in queue
            queue = self._load_queue()
            for detection in queue:
                if detection['id'] == detection_id:
                    detection['status'] = 'emergency'
                    detection['action'] = 'alarm_triggered'
                    detection['alarm_time'] = datetime.now().isoformat()
                    break
            self._save_queue(queue)
            
            # Send emergency alert
            await query.edit_message_text(
                "🚨 *EMERGENCY ALERT TRIGGERED*\n\n"
                "⚠️ Intruder detected and logged\n"
                "📢 Security team notified\n"
                "📸 Evidence saved\n\n"
                "🔒 System on high alert",
                parse_mode='Markdown'
            )
            
            # Send follow-up alert to owner
            await self.app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="🚨🚨🚨 *SECURITY ALERT* 🚨🚨🚨\n\n"
                     "⚠️ Emergency alarm triggered for unknown person\n"
                     "📸 Evidence preserved in database\n"
                     "⏰ Time: " + datetime.now().strftime("%b %d, %Y - %H:%M:%S"),
                parse_mode='Markdown'
            )
            
            logger.warning(f"🚨 EMERGENCY alarm triggered for detection {detection_id}")
            
            # Clear from pending
            if detection_id in self.pending_approvals:
                del self.pending_approvals[detection_id]
            
        except Exception as e:
            logger.error(f"❌ Failed to handle emergency: {e}")


# Global notifier instances (per user)
_notifier_instances: Dict[str, TelegramNotifier] = {}
_default_notifier_user_id: Optional[str] = None
_notifier_init_locks: Dict[str, asyncio.Lock] = {}


def get_notifier(
    user_id: Optional[str] = None,
    bot_token: str = None,
    owner_chat_id: int = None,
    config: dict = None,
    face_recognizer=None,
) -> Optional[TelegramNotifier]:
    """Get or create a Telegram notifier instance (optionally per-user)."""
    global _default_notifier_user_id

    effective_user_id = user_id or _default_notifier_user_id
    if effective_user_id:
        notifier = _notifier_instances.get(effective_user_id)
        if notifier is None and bot_token and owner_chat_id:
            notifier = TelegramNotifier(bot_token, owner_chat_id, config or {}, face_recognizer)
            _notifier_instances[effective_user_id] = notifier
        return notifier

    # Backward-compatible single default instance (stored under key 'default')
    if 'default' not in _notifier_instances and bot_token and owner_chat_id:
        _notifier_instances['default'] = TelegramNotifier(bot_token, owner_chat_id, config or {}, face_recognizer)
        _default_notifier_user_id = 'default'
    return _notifier_instances.get('default')


async def initialize_notifier(
    bot_token: str,
    owner_chat_id: int,
    config: dict = None,
    face_recognizer=None,
    user_id: Optional[str] = None,
):
    """Initialize and start the Telegram notifier (optionally per-user)."""
    global _default_notifier_user_id

    effective_user_id = user_id or 'default'
    _default_notifier_user_id = effective_user_id

    # Ensure only one initializer runs per user at a time
    if effective_user_id not in _notifier_init_locks:
        _notifier_init_locks[effective_user_id] = asyncio.Lock()

    async with _notifier_init_locks[effective_user_id]:
        notifier = get_notifier(effective_user_id, bot_token, owner_chat_id, config, face_recognizer)
        if notifier and not notifier._started:
            await notifier.initialize()
        return notifier


async def shutdown_notifier(user_id: Optional[str] = None):
    """Shutdown a Telegram notifier (one user) or all notifiers (if user_id is None)."""
    global _default_notifier_user_id

    if user_id is None:
        # Shutdown all
        for uid, notifier in list(_notifier_instances.items()):
            try:
                await notifier.shutdown()
            except Exception:
                pass
            _notifier_instances.pop(uid, None)
        _default_notifier_user_id = None
        return

    notifier = _notifier_instances.get(user_id)
    if notifier:
        await notifier.shutdown()
        _notifier_instances.pop(user_id, None)
        if _default_notifier_user_id == user_id:
            _default_notifier_user_id = None
