import io
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total pages and add header/footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header rule
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(40, letter[1] - 40, letter[0] - 40, letter[1] - 40)
        self.drawString(40, letter[1] - 35, "TechTide • AI Skill Gap & Career Roadmap Platform")

        # Footer rule
        self.line(40, 45, letter[0] - 40, 45)
        self.drawString(40, 32, "Confidential Career Evaluation Report • Generated Deterministically")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 40, 32, page_str)
        self.restoreState()


class CareerReportPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.title_style = ParagraphStyle(
            'DocTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0f172a')
        )
        self.subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#475569')
        )
        self.h2_style = ParagraphStyle(
            'Heading2Custom',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#1e293b'),
            spaceBefore=14,
            spaceAfter=6
        )
        self.body_style = ParagraphStyle(
            'BodyCustom',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#334155')
        )
        self.bold_style = ParagraphStyle(
            'BoldCustom',
            parent=self.body_style,
            fontName='Helvetica-Bold'
        )

    def generate(self, user, target_role, score_data, gap_data, roadmap_data=None):
        """
        Generates a PDF report as an in-memory BytesIO buffer.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=55,
            bottomMargin=55
        )

        story = []

        # 1. Header Banner
        story.append(Paragraph("Career Readiness & Roadmap Report", self.title_style))
        gen_time = datetime.now(timezone.utc).strftime("%B %d, %Y")
        story.append(Paragraph(f"Personalized Career Analysis for <b>{user.name}</b> • {gen_time}", self.subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceBefore=2, spaceAfter=14))

        # 2. Executive Summary Block
        score_val = score_data.get('overall_score', 0.0)
        role_title = target_role.title if target_role else "Target Role Not Set"
        hours = user.hours_per_week or 10

        summary_data = [
            [
                Paragraph(f"<b>Candidate:</b> {user.name}<br/><b>Email:</b> {user.email}<br/><b>Study Budget:</b> {hours} hrs/week", self.body_style),
                Paragraph(
                    f"<b>Target Career Role:</b><br/>"
                    f"<font size='13' color='#1d4ed8'><b>{role_title}</b></font><br/>"
                    f"Domain: {target_role.domain if target_role else 'Technology'}",
                    self.body_style
                ),
                Paragraph(
                    f"<b>Career Readiness:</b><br/>"
                    f"<font size='22' color='#16a34a'><b>{score_val}%</b></font><br/>"
                    f"Formula: 100 * Σ(w_i * min(u_i/r_i, 1)) / Σ(w_i)",
                    self.body_style
                )
            ]
        ]
        summary_table = Table(summary_data, colWidths=[2.2*inch, 2.7*inch, 2.3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 14))

        # 3. Category Breakdown & Point Losses
        story.append(Paragraph("Score Breakdown & Point Loss Explanation", self.h2_style))
        story.append(Paragraph(
            "Every readiness score is deterministic and interpretable. Point losses explain exactly which missing skills cost points.",
            self.body_style
        ))
        story.append(Spacer(1, 6))

        point_losses = score_data.get('point_losses', [])
        cat_scores = score_data.get('category_scores', {})

        cat_rows = [["Category", "Proficiency Score", "Status"]]
        for cat, sc in cat_scores.items():
            status_text = "Mastered" if sc >= 85 else ("Proficient" if sc >= 60 else "Requires Focus")
            cat_rows.append([cat, f"{sc}%", status_text])

        if len(cat_rows) > 1:
            cat_table = Table(cat_rows, colWidths=[3.2*inch, 2.0*inch, 2.0*inch])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f1f5f9')]),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(cat_table)
            story.append(Spacer(1, 10))

        if point_losses:
            loss_rows = [["Skill Deficit", "Category", "Weight", "Pts Lost", "Explanation"]]
            for loss in point_losses[:6]:
                loss_rows.append([
                    loss['skill_name'],
                    loss['category'],
                    str(loss['weight']),
                    f"-{loss['points_lost']} pts",
                    Paragraph(loss['explanation'], self.body_style)
                ])

            loss_table = Table(loss_rows, colWidths=[1.4*inch, 1.2*inch, 0.7*inch, 0.9*inch, 3.0*inch])
            loss_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dc2626')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fff1f2')]),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#fecaca')),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(loss_table)
            story.append(Spacer(1, 14))

        # 4. Skill Gap Matrix
        story.append(Paragraph("Skill Gap Classification", self.h2_style))
        gap_summary = gap_data.get('summary', {})
        story.append(Paragraph(
            f"<b>Total Role Skills:</b> {gap_summary.get('total_skills', 0)} | "
            f"<b>Matched:</b> {gap_summary.get('matched_count', 0)} | "
            f"<b>Partial:</b> {gap_summary.get('partial_count', 0)} | "
            f"<b>Missing:</b> {gap_summary.get('missing_count', 0)}",
            self.body_style
        ))
        story.append(Spacer(1, 6))

        gap_rows = [["Skill Name", "Category", "Status", "User Level", "Req Level", "Weight"]]
        all_skills = gap_data.get('matched', []) + gap_data.get('partial', []) + gap_data.get('missing', [])
        for item in all_skills[:12]:
            st = item.get('status', 'missing').capitalize()
            gap_rows.append([
                item['skill_name'],
                item['category'],
                st,
                f"Lvl {item['user_level']}",
                f"Lvl {item['required_level']}",
                str(item['weight'])
            ])

        gap_table = Table(gap_rows, colWidths=[1.8*inch, 1.6*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.8*inch])
        gap_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(gap_table)
        story.append(Spacer(1, 14))

        # 5. Roadmap Section
        if roadmap_data and roadmap_data.get('milestones'):
            story.append(KeepTogether([
                Paragraph("Curated Week-by-Week Learning Roadmap", self.h2_style),
                Paragraph(
                    "Generated via the Agentic Roadmap Loop. Grounded strictly in database resources and validated against weekly hours.",
                    self.body_style
                ),
                Spacer(1, 6)
            ]))

            milestones = roadmap_data.get('milestones', [])
            for m in milestones:
                week_title = f"Week {m.get('week')}: {m.get('title')} ({m.get('status', 'pending').upper()})"
                m_elements = [
                    Paragraph(f"<b>{week_title}</b>", self.bold_style),
                    Spacer(1, 3)
                ]
                
                # Resources & projects if in generated_json
                m_details = m.get('details', {})
                res_list = m_details.get('resources', [])
                if res_list:
                    res_texts = [f"• [{r.get('type', 'Doc').upper()}] {r.get('title')} ({r.get('hours', 2)}h)" for r in res_list]
                    m_elements.append(Paragraph("<br/>".join(res_texts), self.body_style))

                proj = m_details.get('project')
                if proj:
                    m_elements.append(Paragraph(f"<b>Hands-on Project:</b> {proj.get('title')} - {proj.get('description', '')}", self.body_style))

                m_table = Table([[e] for e in m_elements], colWidths=[7.2*inch])
                bg_color = colors.HexColor('#ecfdf5') if m.get('status') == 'completed' else colors.HexColor('#f8fafc')
                border_color = colors.HexColor('#10b981') if m.get('status') == 'completed' else colors.HexColor('#cbd5e1')
                m_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), bg_color),
                    ('BOX', (0,0), (-1,-1), 1, border_color),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(m_table)
                story.append(Spacer(1, 6))

        # Build document
        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer
