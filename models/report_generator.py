"""
Report Generator Module

Generates comprehensive video analysis reports with visualizations.
Produces:
- JSON reports with detailed analysis
- Heatmap visualizations
- Timeline charts
- Frame-by-frame summaries
- PDF export (if available)

Tech Stack:
- OpenCV - Image generation and visualization
- Matplotlib - Charts and graphs
- Pillow - Image generation
- reportlab - PDF generation (optional)
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json
import warnings
import base64
from io import BytesIO

warnings.filterwarnings('ignore')

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ Matplotlib not available. Chart generation will be limited.")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ ReportLab not available. PDF generation will be limited.")


class ReportGenerator:
    """
    Generates comprehensive video analysis reports.
    """
    
    def __init__(self, output_dir: str = "./reports"):
        """
        Args:
            output_dir: Output directory for reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _encode_image_to_base64(image_path: str) -> str:
        """
        Encode image file to base64 data URI.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 data URI string
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            base64_str = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{base64_str}"
        except Exception as e:
            print(f"⚠️ Error encoding image: {e}")
            return ""

    @staticmethod
    def _decode_data_uri_to_bytesio(image_data: str) -> Optional[BytesIO]:
        """Convert a base64 data URI (or bare base64) into a BytesIO stream for ReportLab."""
        try:
            if not image_data:
                return None

            payload = image_data
            if image_data.startswith('data:image'):
                _, payload = image_data.split(',', 1)

            raw = base64.b64decode(payload)
            stream = BytesIO(raw)
            stream.seek(0)
            return stream
        except Exception as e:
            print(f"⚠️ Failed to decode chart image data: {e}")
            return None
    
    def generate_json_report(
        self,
        video_file: str,
        analysis_results: List[Dict],
        video_metadata: Dict,
        advanced_analytics: Dict
    ) -> Dict:
        """
        Generate JSON report of analysis.
        
        Args:
            video_file: Input video filename
            analysis_results: List of frame analysis results
            video_metadata: Metadata about video (fps, duration, etc.)
            advanced_analytics: Advanced analytics from new modules
            
        Returns:
            Report data as dictionary (not file path)
        """
        # Aggregate statistics
        stats = self._calculate_statistics(analysis_results)
        
        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'input_file': video_file,
                'total_frames_analyzed': len(analysis_results),
                **video_metadata
            },
            'statistics': stats,
            'advanced_analytics': advanced_analytics,
            'threshold_violations': self._extract_violations(analysis_results),
            'timeline': self._create_timeline(analysis_results),
            'frame_details': analysis_results[:100]  # Limit for file size
        }
        
        # Reports are saved to MongoDB by the API
        return report
    
    def generate_summary_image(
        self,
        frame: np.ndarray,
        analysis: Dict,
        heatmap: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Generate summary image with annotations.
        
        Args:
            frame: Video frame
            analysis: Analysis result
            heatmap: Optional heatmap overlay
            
        Returns:
            Annotated frame with summary
        """
        h, w = frame.shape[:2]
        
        # Prepare frame copy
        result = frame.copy()
        
        # Overlay heatmap if provided
        if heatmap is not None:
            heatmap_resized = cv2.resize(heatmap, (w, h))
            heatmap_colored = cv2.applyColorMap((heatmap_resized * 255).astype(np.uint8), cv2.COLORMAP_JET)
            result = cv2.addWeighted(result, 0.7, heatmap_colored, 0.3, 0)
        
        # Add summary text box
        risk_level = analysis.get('risk_assessment', {}).get('risk_level', 'UNKNOWN')
        risk_score = analysis.get('risk_assessment', {}).get('overall_score', 0)
        
        # Color based on risk
        if risk_level == 'HIGH':
            color = (0, 0, 255)  # Red
        elif risk_level == 'MEDIUM':
            color = (0, 165, 255)  # Orange
        else:
            color = (0, 255, 0)  # Green
        
        # Draw summary box
        box_h = 150
        box_thickness = 2
        cv2.rectangle(result, (10, 10), (400, 10 + box_h), (0, 0, 0), -1)
        cv2.rectangle(result, (10, 10), (400, 10 + box_h), color, box_thickness)
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        
        texts = [
            f"Risk Level: {risk_level}",
            f"Risk Score: {risk_score:.2%}",
            f"Weapons: {len(analysis.get('suspicious_objects', []))}",
            f"Frame: {analysis.get('frame_number', 0)}"
        ]
        
        y_offset = 40
        for text in texts:
            cv2.putText(result, text, (20, y_offset), font, font_scale, (255, 255, 255), thickness)
            y_offset += 30
        
        return result
    
    def generate_timeline_chart(
        self,
        analysis_results: List[Dict],
        output_file: str = "timeline.png"
    ) -> str:
        """
        Generate timeline chart of risk levels.
        
        Args:
            analysis_results: Frame analysis results
            output_file: Output filename
            
        Returns:
            Base64 encoded image data URI
        """
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️ Matplotlib not available, skipping timeline chart")
            return ""
        
        try:
            frames = []
            risk_scores = []
            risk_levels = []
            
            for r in analysis_results:
                frames.append(r.get('frame_number', len(frames)))
                risk = r.get('risk_assessment', {})
                risk_scores.append(risk.get('overall_score', 0) * 100)
                risk_levels.append(risk.get('risk_level', 'LOW'))
            
            # Create figure
            fig, ax = plt.subplots(figsize=(14, 6), facecolor='#0a0e27')
            ax.set_facecolor('#1a1f3a')
            
            # Plot risk score
            ax.plot(frames, risk_scores, color='#00d4ff', linewidth=2, label='Risk Score')
            ax.fill_between(frames, 0, risk_scores, alpha=0.3, color='#00d4ff')
            
            # Color background by risk level
            for i in range(len(frames) - 1):
                level = risk_levels[i]
                if level == 'HIGH':
                    color = '#ff0000'
                    alpha = 0.15
                elif level == 'MEDIUM':
                    color = '#ffa500'
                    alpha = 0.1
                else:
                    color = '#00ff00'
                    alpha = 0.05
                
                ax.axvspan(frames[i], frames[i+1], alpha=alpha, color=color)
            
            # Formatting
            ax.set_xlabel('Frame Number', color='#ffffff', fontsize=12)
            ax.set_ylabel('Risk Score (%)', color='#ffffff', fontsize=12)
            ax.set_title('Video Analysis Timeline', color='#ffffff', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.2, color='#ffffff')
            ax.legend(loc='upper right', facecolor='#1a1f3a', edgecolor='#00d4ff')
            
            # Set tick colors
            ax.tick_params(colors='#ffffff')
            
            # Save to file and return as base64
            output_path = self.output_dir / output_file
            plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='#0a0e27')
            plt.close()
            
            # Chart is returned as base64 (Reports saved to MongoDB by the API, not stored locally)
            return self._encode_image_to_base64(str(output_path))
        
        except Exception as e:
            print(f"⚠️ Error generating timeline chart: {e}")
            return ""
    
    def generate_statistics_chart(
        self,
        advanced_analytics: Dict,
        output_file: str = "statistics.png"
    ) -> str:
        """
        Generate statistics visualization.
        
        Args:
            advanced_analytics: Analytics from advanced modules
            output_file: Output filename
            
        Returns:
            Base64 encoded image data URI
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10), facecolor='#0a0e27')
            
            for ax in [ax1, ax2, ax3, ax4]:
                ax.set_facecolor('#1a1f3a')
                ax.tick_params(colors='#ffffff')
            
            # 1. Activity Distribution
            activities = advanced_analytics.get('activity_summary', {})
            if activities and len(activities) > 0:
                try:
                    # Extract numeric values from activity data
                    activity_names = []
                    activity_counts = []
                    for key, value in activities.items():
                        activity_names.append(str(key))
                        # Handle both dict and numeric values
                        if isinstance(value, dict):
                            activity_counts.append(value.get('count', 0))
                        else:
                            activity_counts.append(float(value) if value else 0)
                    
                    if activity_counts and any(c > 0 for c in activity_counts):
                        ax1.bar(activity_names, activity_counts, color='#00d4ff', edgecolor='#ffffff')
                        ax1.set_title('Activity Distribution', color='#ffffff', fontweight='bold')
                        ax1.set_ylabel('Count', color='#ffffff')
                        ax1.tick_params(axis='x', rotation=45)
                    else:
                        ax1.text(0.5, 0.5, 'No Activity Data', ha='center', va='center', color='#ffffff', fontsize=12)
                except Exception as e:
                    ax1.text(0.5, 0.5, f'Error: {str(e)[:20]}', ha='center', va='center', color='#ff0000', fontsize=10)
            else:
                ax1.text(0.5, 0.5, 'No Activity Data', ha='center', va='center', color='#ffffff', fontsize=12)
            
            # 2. Incident Totals (uses current pipeline schema)
            try:
                anomalies = advanced_analytics.get('anomalies_detected', [])
                loitering = advanced_analytics.get('loitering_incidents', [])
                unusual = advanced_analytics.get('unusual_movements', [])
                object_motion = advanced_analytics.get('object_motion_events', [])

                incident_names = ['Anomalies', 'Loitering', 'Unusual', 'Object Motion']
                incident_counts = [
                    len(anomalies) if isinstance(anomalies, list) else 0,
                    len(loitering) if isinstance(loitering, list) else 0,
                    len(unusual) if isinstance(unusual, list) else 0,
                    len(object_motion) if isinstance(object_motion, list) else 0,
                ]

                if any(c > 0 for c in incident_counts):
                    ax2.bar(
                        incident_names,
                        incident_counts,
                        color=['#ff69b4', '#f59e0b', '#8b5cf6', '#06b6d4'],
                        edgecolor='#ffffff',
                    )
                    ax2.set_title('Incident Overview', color='#ffffff', fontweight='bold')
                    ax2.set_ylabel('Count', color='#ffffff')
                    ax2.tick_params(axis='x', rotation=15)
                else:
                    ax2.text(0.5, 0.5, 'No Incident Data', ha='center', va='center', color='#ffffff', fontsize=12)
            except Exception as e:
                ax2.text(0.5, 0.5, f'Error: {str(e)[:20]}', ha='center', va='center', color='#ff0000', fontsize=10)
            
            # 3. Crowd Density Over Time
            crowd_timeline = advanced_analytics.get('crowd_density_timeline', [])
            if crowd_timeline and len(crowd_timeline) > 0:
                try:
                    # Handle both list of dicts and list of numbers
                    density_values = []
                    for item in crowd_timeline:
                        if isinstance(item, dict):
                            density_values.append(item.get('person_count', item.get('density', 0)))
                        else:
                            density_values.append(float(item) if item else 0)
                    
                    if density_values and any(d > 0 for d in density_values):
                        ax3.plot(range(len(density_values)), density_values, color='#00ff00', linewidth=2)
                        ax3.fill_between(range(len(density_values)), 0, density_values, alpha=0.3, color='#00ff00')
                        ax3.set_title('Crowd Density Over Time', color='#ffffff', fontweight='bold')
                        ax3.set_xlabel('Frame', color='#ffffff')
                        ax3.set_ylabel('Person Count', color='#ffffff')
                    else:
                        ax3.text(0.5, 0.5, 'No Crowd Data', ha='center', va='center', color='#ffffff', fontsize=12)
                except Exception as e:
                    ax3.text(0.5, 0.5, f'Error: {str(e)[:20]}', ha='center', va='center', color='#ff0000', fontsize=10)
            else:
                ax3.text(0.5, 0.5, 'No Crowd Data', ha='center', va='center', color='#ffffff', fontsize=12)
            
            # 4. Anomaly Severity Distribution
            anomaly_events = advanced_analytics.get('anomalies_detected', [])
            if anomaly_events and len(anomaly_events) > 0:
                try:
                    severity_counts = {}
                    for event in anomaly_events:
                        if isinstance(event, dict):
                            severity = str(event.get('severity', 'UNKNOWN')).upper()
                        else:
                            severity = 'UNKNOWN'
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

                    sev_names = list(severity_counts.keys())
                    sev_values = list(severity_counts.values())
                    sev_colors = [
                        '#ef4444' if s == 'HIGH' else '#f59e0b' if s == 'MEDIUM' else '#3b82f6'
                        for s in sev_names
                    ]

                    ax4.bar(sev_names, sev_values, color=sev_colors, edgecolor='#ffffff')
                    ax4.set_title('Anomaly Severity', color='#ffffff', fontweight='bold')
                    ax4.set_ylabel('Count', color='#ffffff')
                except Exception as e:
                    ax4.text(0.5, 0.5, f'Error: {str(e)[:20]}', ha='center', va='center', color='#ff0000', fontsize=10)
            else:
                ax4.text(0.5, 0.5, 'No Anomalies', ha='center', va='center', color='#ffffff', fontsize=12)
            
            plt.tight_layout()
            
            output_path = self.output_dir / output_file
            plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='#0a0e27')
            plt.close()
            
            # Chart is returned as base64 (Reports saved to MongoDB by the API, not stored locally)
            return self._encode_image_to_base64(str(output_path))
        
        except Exception as e:
            print(f"⚠️ Error generating statistics chart: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def generate_pdf_report(
        self,
        video_file: str,
        analysis_results: List[Dict],
        advanced_analytics: Dict,
        summary_image: Optional[np.ndarray] = None,
        timeline_chart: Optional[str] = None,
        statistics_chart: Optional[str] = None
    ) -> str:
        """
        Generate PDF report.
        
        Args:
            video_file: Video filename
            analysis_results: Frame results
            advanced_analytics: Advanced analytics
            summary_image: Summary frame image
            timeline_chart: Timeline chart path
            statistics_chart: Statistics chart path
            
        Returns:
            Path to PDF report
        """
        if not REPORTLAB_AVAILABLE:
            print("⚠️ ReportLab not available, skipping PDF generation")
            return ""
        
        try:
            pdf_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = self.output_dir / pdf_name
            
            # Create PDF
            doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#00d4ff'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph("Video Analysis Report", title_style))
            story.append(Spacer(1, 12))
            
            # Metadata
            stats = self._calculate_statistics(analysis_results)
            metadata_text = f"""
            <b>File:</b> {video_file}<br/>
            <b>Analysis Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
            <b>Total Frames:</b> {len(analysis_results)}<br/>
            <b>Duration:</b> {stats.get('duration_seconds', 'N/A')}s
            """
            story.append(Paragraph(metadata_text, styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Summary statistics
            summary_text = f"""
            <b>Risk Summary:</b><br/>
            High Risk Frames: {stats.get('high_risk_frames', 0)}<br/>
            Medium Risk Frames: {stats.get('medium_risk_frames', 0)}<br/>
            Low Risk Frames: {stats.get('low_risk_frames', 0)}<br/>
            Average Risk Score: {stats.get('avg_risk_score', 0):.2%}
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Add timeline chart (supports both local file path and base64 data URI)
            if timeline_chart:
                story.append(Paragraph("<b>Risk Timeline</b>", styles['Heading2']))
                chart_added = False
                if isinstance(timeline_chart, str) and timeline_chart.startswith('data:image'):
                    timeline_stream = self._decode_data_uri_to_bytesio(timeline_chart)
                    if timeline_stream is not None:
                        img = Image(timeline_stream, width=6*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))
                        chart_added = True
                elif isinstance(timeline_chart, str) and Path(timeline_chart).exists():
                    img = Image(timeline_chart, width=6*inch, height=3*inch)
                    story.append(img)
                    story.append(Spacer(1, 12))
                    chart_added = True

                if not chart_added:
                    story.append(Paragraph("Timeline chart unavailable", styles['Normal']))
                    story.append(Spacer(1, 12))
            
            # Add statistics chart (supports both local file path and base64 data URI)
            if statistics_chart:
                story.append(PageBreak())
                story.append(Paragraph("<b>Detailed Statistics</b>", styles['Heading2']))
                chart_added = False
                if isinstance(statistics_chart, str) and statistics_chart.startswith('data:image'):
                    stats_stream = self._decode_data_uri_to_bytesio(statistics_chart)
                    if stats_stream is not None:
                        img = Image(stats_stream, width=6*inch, height=5*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))
                        chart_added = True
                elif isinstance(statistics_chart, str) and Path(statistics_chart).exists():
                    img = Image(statistics_chart, width=6*inch, height=5*inch)
                    story.append(img)
                    story.append(Spacer(1, 12))
                    chart_added = True

                if not chart_added:
                    story.append(Paragraph("Statistics chart unavailable", styles['Normal']))
                    story.append(Spacer(1, 12))
            
            # Advanced analytics summary
            story.append(PageBreak())
            story.append(Paragraph("<b>Advanced Analytics</b>", styles['Heading2']))
            
            for key, value in advanced_analytics.items():
                if isinstance(value, dict):
                    analytics_text = f"<b>{key}:</b><br/>"
                    for k, v in value.items():
                        analytics_text += f"{k}: {v}<br/>"
                    story.append(Paragraph(analytics_text, styles['Normal']))
                    story.append(Spacer(1, 6))
            
            # Build PDF
            doc.build(story)
            
            print(f"✅ PDF Report saved: {pdf_path}")
            return str(pdf_path)
        
        except Exception as e:
            print(f"⚠️ Error generating PDF report: {e}")
            return ""
    
    def _calculate_statistics(self, results: List[Dict]) -> Dict:
        """Calculate statistics from analysis results"""
        if not results:
            return {}
        
        risk_levels = [r.get('risk_assessment', {}).get('risk_level', 'LOW') for r in results]
        risk_scores = [r.get('risk_assessment', {}).get('overall_score', 0) for r in results]
        
        return {
            'total_frames': len(results),
            'high_risk_frames': sum(1 for l in risk_levels if l == 'HIGH'),
            'medium_risk_frames': sum(1 for l in risk_levels if l == 'MEDIUM'),
            'low_risk_frames': sum(1 for l in risk_levels if l == 'LOW'),
            'avg_risk_score': np.mean(risk_scores) if risk_scores else 0,
            'max_risk_score': np.max(risk_scores) if risk_scores else 0,
            'min_risk_score': np.min(risk_scores) if risk_scores else 0,
            'duration_seconds': len(results) / 30  # Assume 30 fps
        }
    
    def _extract_violations(self, results: List[Dict]) -> List[Dict]:
        """Extract high-risk frames"""
        violations = []
        for r in results:
            if r.get('risk_assessment', {}).get('risk_level') == 'HIGH':
                violations.append({
                    'frame': r.get('frame_number'),
                    'reason': r.get('summary'),
                    'score': r.get('risk_assessment', {}).get('overall_score')
                })
        return violations[:50]  # Limit to 50
    
    def _create_timeline(self, results: List[Dict]) -> List[Dict]:
        """Create frame-by-frame timeline"""
        timeline = []
        for r in results[::10]:  # Every 10th frame
            timeline.append({
                'frame': r.get('frame_number'),
                'risk_level': r.get('risk_assessment', {}).get('risk_level'),
                'summary': r.get('summary')
            })
        return timeline
