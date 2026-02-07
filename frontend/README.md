# VisionGuard AI - React Frontend Setup

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The frontend will be available at: **http://localhost:3000**

### 3. Start Backend API

In a separate terminal:

```bash
# From project root
python api/main.py
```

The backend API will run at: **http://localhost:8000**

## ✨ Features

### Modern Tech Stack
- **React 18** - Latest React with hooks
- **Vite** - Lightning-fast build tool
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Smooth animations
- **Lucide React** - Beautiful icons
- **Axios** - HTTP client for API calls

### UI/UX Features
- ✅ Modern gradient design
- ✅ Smooth animations and transitions
- ✅ Responsive layout
- ✅ Glassmorphism effects
- ✅ Interactive components
- ✅ Professional color schemes
- ✅ Drag & drop file upload
- ✅ Real-time analysis results

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar.jsx          # Navigation sidebar
│   │   ├── StatsCard.jsx        # Statistics display card
│   │   └── RiskBadge.jsx        # Risk level indicator
│   ├── pages/
│   │   ├── Dashboard.jsx        # Main dashboard
│   │   ├── ImageAnalysis.jsx    # Image upload & analysis
│   │   ├── VideoAnalysis.jsx    # Video processing (coming soon)
│   │   ├── LiveCCTV.jsx         # Live monitoring (coming soon)
│   │   └── FaceDatabase.jsx     # Face management (coming soon)
│   ├── App.jsx                  # Main app component
│   ├── main.jsx                 # Entry point
│   └── index.css                # Global styles
├── package.json                 # Dependencies
├── vite.config.js              # Vite configuration
├── tailwind.config.js          # Tailwind configuration
└── postcss.config.js           # PostCSS configuration
```

## 🎨 Design System

### Colors
- **Primary**: Purple/Blue gradient (#667eea → #764ba2)
- **Danger**: Red/Pink gradient (#FF416C → #FF4B2B)
- **Success**: Green/Teal gradient (#96FBC4 → #00B4DB)
- **Warning**: Yellow/Orange gradient (#FFD89B → #FF9A9E)

### Typography
- **Font**: Inter (Google Fonts)
- **Headings**: Bold 700-800
- **Body**: Regular 400-500

### Components
- **Cards**: White background with shadow and rounded corners
- **Buttons**: Gradient backgrounds with hover effects
- **Badges**: Color-coded by risk level
- **Animations**: Smooth transitions using Framer Motion

## 🔌 API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000`

### Endpoints Used
- `POST /api/analyze/image` - Analyze uploaded image
- `POST /api/analyze/video` - Analyze video (coming soon)
- `GET /api/database/faces` - Get registered faces (coming soon)
- `POST /api/database/faces` - Add new face (coming soon)

## 🛠️ Development

### Install new package
```bash
npm install package-name
```

### Build for production
```bash
npm run build
```

### Preview production build
```bash
npm run preview
```

## 📱 Pages Overview

### 1. Dashboard
- System overview
- Quick statistics
- AI capabilities showcase
- Quick action buttons

### 2. Image Analysis
- Drag & drop image upload
- Real-time analysis
- Risk assessment display
- Detailed threat breakdown
- Annotated image results

### 3. Video Analysis (Coming Soon)
- Video upload
- Frame-by-frame processing
- Timeline visualization
- Batch analysis results

### 4. Live CCTV (Coming Soon)
- Real-time camera feed
- Continuous monitoring
- Instant threat alerts
- Live metrics dashboard

### 5. Face Database (Coming Soon)
- View registered identities
- Add new faces
- Remove identities
- Face recognition management

## 🎯 Next Steps

1. Complete Video Analysis page
2. Complete Live CCTV page
3. Complete Face Database page
4. Add user authentication
5. Add analytics dashboard
6. Add export functionality

## 💡 Tips

- Use `npm run dev` for hot-reload during development
- Check browser console for errors
- Make sure backend API is running before testing
- All API calls are proxied through Vite dev server

## 🐛 Troubleshooting

### Port already in use
```bash
# Kill process on port 3000
npx kill-port 3000
```

### Dependencies not installing
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### API connection issues
- Ensure backend is running on port 8000
- Check proxy settings in vite.config.js
- Verify CORS settings in FastAPI

## 📞 Support

For issues or questions, check the main project README or contact the development team.

---

**Built with ❤️ using React + Tailwind CSS**
