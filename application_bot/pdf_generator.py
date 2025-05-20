# application_bot/pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER # Removed TA_LEFT, TA_RIGHT as they were not used here.
from PIL import Image as PILImage
import os
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

from application_bot import utils # utils.SETTINGS and utils.QUESTIONS will be accessed here
from application_bot.utils import get_text, get_external_file_path

logger = logging.getLogger(__name__)

# No longer need _font_registered global flag here

def _get_and_register_font_from_settings() -> str:
    """
    Determines the font to use based on settings, attempts to register it,
    and returns the font name to be used in PDF styles.
    Falls back to "Helvetica" if custom font is not specified, not found, or fails to register.
    """
    default_font_name = "Helvetica" # ReportLab's default

    if not utils.SETTINGS:
        logger.warning("PDF Generator: SETTINGS not loaded. Falling back to default font '%s'.", default_font_name)
        return default_font_name

    pdf_cfg = utils.SETTINGS.get("PDF_SETTINGS", {})
    font_name_to_register = pdf_cfg.get("font_name_registered", "CustomUnicodeFont") # The alias for reportlab
    font_file_relative_path = utils.SETTINGS.get("FONT_FILE_PATH")

    if not font_file_relative_path:
        logger.warning(
            "PDF Generator: FONT_FILE_PATH not set in settings.json. "
            "Using fallback font '%s'. PDF might not support all characters.", default_font_name
        )
        return default_font_name

    font_abs_path = get_external_file_path(font_file_relative_path)

    if not os.path.exists(font_abs_path):
        logger.error(
            "PDF Generator: Font file not found at '%s'. "
            "Using fallback font '%s'. PDF generation might fail or use fallback.",
            font_abs_path, default_font_name
        )
        return default_font_name

    try:
        # Attempt to register the font. If it's already registered with the same name and TTFont object,
        # reportlab usually handles this gracefully.
        # If the font file or name changed, this will register the new one.
        pdfmetrics.registerFont(TTFont(font_name_to_register, font_abs_path))
        logger.info("PDF Generator: Successfully registered font '%s' from '%s'.", font_name_to_register, font_abs_path)
        return font_name_to_register # Use the custom registered font name
    except Exception as e:
        logger.error(
            "PDF Generator: Error registering font '%s' from '%s': %s. "
            "Falling back to '%s'.",
            font_name_to_register, font_abs_path, e, default_font_name
        )
        return default_font_name


def create_application_pdf(user_id: int, username: Optional[str], answers: Dict[str, str],
                           photo_file_paths: List[str],
                           user_lang: str) -> Optional[str]:
    if not utils.SETTINGS or not utils.QUESTIONS:
        logger.error("PDF Generator: Settings or Questions not loaded. Cannot generate PDF.")
        return None

    # Determine and register the font to be used for this PDF generation.
    # This will use the latest settings.
    actual_font_name_for_pdf = _get_and_register_font_from_settings()
    logger.debug("PDF Generator: Using font '%s' for PDF generation.", actual_font_name_for_pdf)

    pdf_cfg = utils.SETTINGS.get("PDF_SETTINGS", {}) # Get PDF_SETTINGS again for other configs

    app_folder_name = utils.SETTINGS.get("APPLICATION_FOLDER", "applications")
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

        # Use the determined (and possibly newly registered) font name
        title_style = ParagraphStyle('PdfTitle', parent=styles['h1'], fontName=actual_font_name_for_pdf,
                                     fontSize=pdf_cfg.get("title_font_size", 16),
                                     alignment=TA_CENTER, spaceAfter=6*mm)

        header_style = ParagraphStyle('PdfHeaderInfo', parent=styles['Normal'], fontName=actual_font_name_for_pdf,
                                      fontSize=pdf_cfg.get("header_font_size", 10), spaceAfter=2*mm)

        question_style = ParagraphStyle('PdfQuestion', parent=styles['Normal'], fontName=actual_font_name_for_pdf,
                                        fontSize=pdf_cfg.get("question_font_size", 12),
                                        leading=pdf_cfg.get("question_font_size", 12) * 1.2,
                                        fontWeight='bold' if pdf_cfg.get("question_bold", True) else 'normal',
                                        spaceAfter=1*mm)

        answer_style = ParagraphStyle('PdfAnswer', parent=styles['Normal'], fontName=actual_font_name_for_pdf,
                                      fontSize=pdf_cfg.get("answer_font_size", 10),
                                      leading=pdf_cfg.get("answer_font_size", 10) * 1.2,
                                      leftIndent=0,
                                      spaceAfter=3*mm)

        story.append(Paragraph(get_text("pdf_header", user_lang), title_style))
        username_display = username if username else "N/A"
        story.append(Paragraph(get_text("pdf_applicant_info", user_lang, username=username_display, user_id=user_id), header_style))
        story.append(Paragraph(get_text("pdf_submission_time", user_lang, submission_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")), header_style))
        story.append(Spacer(1, 5 * mm))

        photo_pos = pdf_cfg.get("photo_position", "top_right")
        photo_width_mm = pdf_cfg.get("photo_width_mm", 40)
        max_photo_pixel_width = 800 # Consider making this configurable in PDF_SETTINGS

        for photo_path in photo_file_paths:
            if not os.path.exists(photo_path):
                logger.warning(f"PDF Generator: Photo file not found for PDF: {photo_path}")
                story.append(Paragraph(f"[Image not found: {os.path.basename(photo_path)}]", answer_style))
                continue
            try:
                pil_img = PILImage.open(photo_path)
                original_width, original_height = pil_img.size

                if original_width > max_photo_pixel_width:
                    aspect_ratio = original_height / original_width
                    new_width = max_photo_pixel_width
                    new_height = int(new_width * aspect_ratio)
                    pil_img = pil_img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

                img = Image(photo_path, width=photo_width_mm * mm, height=(photo_width_mm * mm * (pil_img.height / pil_img.width)))

                if photo_pos == "center": img.hAlign = 'CENTER'
                # Add more alignment options if needed (e.g., 'LEFT', 'RIGHT')

                story.append(img)
                story.append(Spacer(1, 3 * mm))
            except Exception as e:
                logger.error(f"PDF Generator: Error adding image {photo_path} to PDF: {e}", exc_info=True)
                story.append(Paragraph(f"[Error loading image: {os.path.basename(photo_path)}]", answer_style))

        story.append(Spacer(1, 5 * mm))

        for q_data in utils.QUESTIONS:
            q_id = q_data["id"]
            q_text_from_json = q_data["text"]
            answer_text = answers.get(q_id, get_text("not_answered_placeholder", user_lang, default="[No Answer Given]"))

            story.append(Paragraph(q_text_from_json, question_style))
            story.append(Paragraph(answer_text, answer_style))
            story.append(Spacer(1, 2*mm))

        doc.build(story)
        logger.info(f"PDF Generator: PDF generated successfully: {pdf_filepath}")
        return pdf_filepath

    except Exception as e:
        logger.error(f"PDF Generator: Failed to generate PDF for user {user_id}: {e}", exc_info=True)
        if os.path.exists(pdf_filepath):
            try:
                os.remove(pdf_filepath)
            except OSError:
                logger.warning(f"PDF Generator: Could not remove partially created PDF: {pdf_filepath}")
        return None