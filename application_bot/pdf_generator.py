# telegram_application_bot/pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage # For pre-processing images
import os
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

# Assuming utils.py is in the parent directory or Python path is set up
# For direct execution or if in a package structure:
try:
    from application_bot.utils import SETTINGS, QUESTIONS, get_text, get_external_file_path
except ImportError:
    from application_bot.utils import SETTINGS, QUESTIONS, get_text, get_external_file_path


logger = logging.getLogger(__name__)
_font_registered = False

def register_font_if_needed():
    # (Same as before, ensure it uses SETTINGS["PDF_SETTINGS"]["font_name_registered"])
    global _font_registered
    if _font_registered or not SETTINGS:
        return

    pdf_cfg = SETTINGS.get("PDF_SETTINGS", {})
    font_name_registered = pdf_cfg.get("font_name_registered", "CustomUnicodeFont")
    font_file_relative_path = SETTINGS.get("FONT_FILE_PATH")

    if not font_file_relative_path:
        logger.warning("FONT_FILE_PATH not set in settings.json. PDF font might not support all characters.")
        SETTINGS["PDF_SETTINGS"]["font_name_registered"] = "Helvetica" # Fallback
        _font_registered = True 
        return

    font_abs_path = get_external_file_path(font_file_relative_path)

    if not os.path.exists(font_abs_path):
        logger.error(f"Font file not found at {font_abs_path}. PDF generation might fail or use fallback font.")
        SETTINGS["PDF_SETTINGS"]["font_name_registered"] = "Helvetica" # Fallback
        _font_registered = True
        return
        
    try:
        pdfmetrics.registerFont(TTFont(font_name_registered, font_abs_path))
        _font_registered = True
        logger.info(f"Successfully registered font: {font_name_registered} from {font_abs_path}")
    except Exception as e:
        logger.error(f"Error registering font {font_abs_path} as {font_name_registered}: {e}. Falling back to Helvetica.")
        SETTINGS["PDF_SETTINGS"]["font_name_registered"] = "Helvetica"
        _font_registered = True

def create_application_pdf(user_id: int, username: Optional[str], answers: Dict[str, str],
                           photo_file_paths: List[str], # List of file paths for local photos
                           user_lang: str) -> Optional[str]:
    if not SETTINGS or not QUESTIONS:
        logger.error("Settings or Questions not loaded. Cannot generate PDF.")
        return None
        
    register_font_if_needed()

    pdf_cfg = SETTINGS["PDF_SETTINGS"]
    actual_font_name = pdf_cfg.get("font_name_registered", "Helvetica")

    app_folder_name = SETTINGS.get("APPLICATION_FOLDER", "applications")
    app_folder_path = get_external_file_path(app_folder_name)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"application_{user_id}_{timestamp}.pdf"
    pdf_filepath = os.path.join(app_folder_path, pdf_filename)

    try:
        doc = SimpleDocTemplate(pdf_filepath,
                                pagesize=(pdf_cfg.get("page_width_mm", 210) * mm, pdf_cfg.get("page_height_mm", 297) * mm),
                                leftMargin=pdf_cfg.get("margin_mm", 15) * mm,
                                rightMargin=pdf_cfg.get("margin_mm", 15) * mm,
                                topMargin=pdf_cfg.get("margin_mm", 15) * mm,
                                bottomMargin=pdf_cfg.get("margin_mm", 15) * mm)
        
        story = []
        styles = getSampleStyleSheet()

        # Define styles based on settings.json
        title_style = ParagraphStyle('PdfTitle', parent=styles['h1'], fontName=actual_font_name, 
                                     fontSize=pdf_cfg.get("title_font_size", 16), 
                                     alignment=TA_CENTER, spaceAfter=6*mm)
        
        header_style = ParagraphStyle('PdfHeaderInfo', parent=styles['Normal'], fontName=actual_font_name,
                                      fontSize=pdf_cfg.get("header_font_size", 10), spaceAfter=2*mm)

        question_style = ParagraphStyle('PdfQuestion', parent=styles['Normal'], fontName=actual_font_name,
                                        fontSize=pdf_cfg.get("question_font_size", 12), # Made slightly larger by default
                                        leading=pdf_cfg.get("question_font_size", 12) * 1.2,
                                        fontWeight='bold' if pdf_cfg.get("question_bold", True) else 'normal',
                                        spaceAfter=1*mm)
        
        answer_style = ParagraphStyle('PdfAnswer', parent=styles['Normal'], fontName=actual_font_name,
                                      fontSize=pdf_cfg.get("answer_font_size", 10),
                                      leading=pdf_cfg.get("answer_font_size", 10) * 1.2,
                                      leftIndent=0, # No indent needed
                                      spaceAfter=3*mm)

        story.append(Paragraph(get_text("pdf_header", user_lang), title_style))
        username_display = username if username else "N/A"
        story.append(Paragraph(get_text("pdf_applicant_info", user_lang, username=username_display, user_id=user_id), header_style))
        story.append(Paragraph(get_text("pdf_submission_time", user_lang, submission_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")), header_style))
        story.append(Spacer(1, 5 * mm))
        
        photo_pos = pdf_cfg.get("photo_position", "top_right") # For future complex layout
        photo_width_mm = pdf_cfg.get("photo_width_mm", 40) 
        max_photo_pixel_width = 800 # Resize to this width if source is larger, to optimize PDF size/quality

        for photo_path in photo_file_paths:
            if not os.path.exists(photo_path):
                logger.warning(f"Photo file not found for PDF: {photo_path}")
                story.append(Paragraph(f"[Image not found: {os.path.basename(photo_path)}]", answer_style))
                continue
            try:
                # Pre-process with Pillow for better quality control
                pil_img = PILImage.open(photo_path)
                original_width, original_height = pil_img.size
                
                # Optional: Resize if image is very large to optimize
                if original_width > max_photo_pixel_width:
                    aspect_ratio = original_height / original_width
                    new_width = max_photo_pixel_width
                    new_height = int(new_width * aspect_ratio)
                    pil_img = pil_img.resize((new_width, new_height), PILImage.Resampling.LANCZOS) # High quality downscaling
                    
                    # Save to a new temp path or overwrite (be careful with overwriting)
                    # For simplicity, let's use the same path if we modify it, or use a temp path
                    # For now, we'll assume the passed photo_path is fine, or we'd need to manage another temp file.
                    # The key is using a good resampling algorithm if resizing.

                # ReportLab Image: width is in points (1mm = 2.83 points approx)
                img = Image(photo_path, width=photo_width_mm * mm, height=(photo_width_mm * mm * (pil_img.height / pil_img.width))) # Maintain aspect ratio
                
                if photo_pos == "center": img.hAlign = 'CENTER'
                # elif photo_pos == "top_right": img.hAlign = 'RIGHT' # Simple alignment
                # elif photo_pos == "top_left": img.hAlign = 'LEFT'   # Simple alignment
                # True corner placement with text flow needs Frames/PageTemplates.
                
                story.append(img)
                story.append(Spacer(1, 3 * mm))
            except Exception as e:
                logger.error(f"Error adding image {photo_path} to PDF: {e}", exc_info=True)
                story.append(Paragraph(f"[Error loading image: {os.path.basename(photo_path)}]", answer_style))

        story.append(Spacer(1, 5 * mm))

        for q_data in QUESTIONS:
            q_id = q_data["id"]
            q_text_from_json = q_data["text"]
            answer_text = answers.get(q_id, get_text("not_answered_placeholder", user_lang, default="[No Answer Given]"))

            story.append(Paragraph(q_text_from_json, question_style))
            story.append(Paragraph(answer_text, answer_style))
            story.append(Spacer(1, 2*mm)) # Space between Q/A pairs
        
        doc.build(story)
        logger.info(f"PDF generated successfully: {pdf_filepath}")
        return pdf_filepath

    except Exception as e:
        logger.error(f"Failed to generate PDF for user {user_id}: {e}", exc_info=True)
        if os.path.exists(pdf_filepath):
            try:
                os.remove(pdf_filepath)
            except OSError:
                logger.warning(f"Could not remove partially created PDF: {pdf_filepath}")
        return None