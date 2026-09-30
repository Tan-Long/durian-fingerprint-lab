#!/usr/bin/env python3
"""Build the combined durian fingerprint and quality-prediction proposal PDF."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/bao-cao-hai-du-an-ai-sau-rieng.pdf"
ASSETS = ROOT / "output/pdf/assets"
W, H = landscape(A4)

INK = colors.HexColor("#17332D")
GREEN = colors.HexColor("#1F6F50")
DEEP = colors.HexColor("#0B2A23")
MINT = colors.HexColor("#DDEDE4")
PALE = colors.HexColor("#F4F1E8")
WHITE = colors.white
GOLD = colors.HexColor("#D9A441")
CYAN = colors.HexColor("#27AAA5")
RED = colors.HexColor("#C95A4A")
MUTED = colors.HexColor("#60766F")
LINE = colors.HexColor("#CAD8D1")


def register_fonts():
    pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))


def style(size=10, leading=None, color=INK, bold=False, align=TA_LEFT):
    return ParagraphStyle(
        name=f"s-{size}-{bold}-{align}-{color}",
        fontName="Arial-Bold" if bold else "Arial",
        fontSize=size,
        leading=leading or size * 1.35,
        textColor=color,
        alignment=align,
        spaceAfter=0,
    )


BODY = None
SMALL = None
TINY = None


def ptext(c, text, x, top, width, text_style=None):
    paragraph = Paragraph(text, text_style or BODY)
    _, height = paragraph.wrap(width, H)
    paragraph.drawOn(c, x, top - height)
    return top - height


def bullets(c, items, x, top, width, text_style=None, gap=5, bullet_color=GREEN):
    text_style = text_style or BODY
    y = top
    for item in items:
        c.setFillColor(bullet_color)
        c.circle(x + 3, y - 6, 2.2, fill=1, stroke=0)
        y = ptext(c, item, x + 12, y, width - 12, text_style) - gap
    return y


def image_cover(c, path, x, y, width, height, anchor_y=0.5):
    image = ImageReader(str(path))
    iw, ih = image.getSize()
    scale = max(width / iw, height / ih)
    dw, dh = iw * scale, ih * scale
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, width, height)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(image, x + (width - dw) / 2, y + (height - dh) * anchor_y, dw, dh, mask="auto")
    c.restoreState()


def image_contain(c, path, x, y, width, height, pad=0):
    image = ImageReader(str(path))
    iw, ih = image.getSize()
    scale = min((width - 2 * pad) / iw, (height - 2 * pad) / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(image, x + (width - dw) / 2, y + (height - dh) / 2, dw, dh, mask="auto")


def rounded(c, x, y, width, height, fill=WHITE, stroke=LINE, radius=10):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def chip(c, text, x, y, width, fill=MINT, color=GREEN):
    c.setFillColor(fill)
    c.roundRect(x, y, width, 22, 11, fill=1, stroke=0)
    ptext(c, escape(text), x + 7, y + 16, width - 14, style(8.5, 10, color, True, TA_CENTER))


def arrow(c, x1, y1, x2, y2, color=GREEN, width=1.8):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = (x2, y2)
    left = (x2 - 8 * ux + 4 * px, y2 - 8 * uy + 4 * py)
    right = (x2 - 8 * ux - 4 * px, y2 - 8 * uy - 4 * py)
    path = c.beginPath()
    path.moveTo(*tip)
    path.lineTo(*left)
    path.lineTo(*right)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def node(c, x, y, width, height, title, detail="", fill=WHITE, accent=GREEN):
    rounded(c, x, y, width, height, fill, LINE, 8)
    c.setFillColor(accent)
    c.roundRect(x, y, 5, height, 3, fill=1, stroke=0)
    top = y + height - 12
    top = ptext(c, escape(title), x + 14, top, width - 24, style(10, 12, INK, True))
    if detail:
        ptext(c, escape(detail), x + 14, top - 4, width - 24, style(7.8, 10, MUTED))


def section_header(c, page_no, kicker, title, subtitle=""):
    c.setFillColor(PALE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    ptext(c, escape(kicker.upper()), 38, H - 28, W - 76, style(8.5, 10, GREEN, True))
    ptext(c, escape(title), 38, H - 48, W - 76, style(24, 28, INK, True))
    if subtitle:
        ptext(c, escape(subtitle), 38, H - 80, W - 76, style(10, 14, MUTED))
    footer(c, page_no)


def footer(c, page_no):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(38, 25, W - 38, 25)
    ptext(c, "BẢN THẢO ĐỀ XUẤT  |  04.09.2026", 38, 20, 250, style(7.5, 9, MUTED, True))
    ptext(c, f"{page_no:02d}", W - 63, 20, 25, style(7.5, 9, MUTED, True, TA_CENTER))


def simple_table(c, data, x, top, widths, header=True, font_size=8.2, row_padding=6):
    rows = []
    for row_index, row in enumerate(data):
        rows.append([
            Paragraph(
                str(cell),
                style(font_size, font_size * 1.3, WHITE if header and row_index == 0 else INK,
                      header and row_index == 0),
            )
            for cell in row
        ])
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DEEP if header else WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), row_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), row_padding),
        ("TOPPADDING", (0, 0), (-1, -1), row_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), row_padding),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
    ]
    for index in range(1 if header else 0, len(rows)):
        commands.append(("BACKGROUND", (0, index), (-1, index), WHITE if index % 2 else colors.HexColor("#EEF3EF")))
    table.setStyle(TableStyle(commands))
    _, height = table.wrap(sum(widths), H)
    table.drawOn(c, x, top - height)
    return top - height


def cover(c):
    c.setFillColor(DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    image_cover(c, ASSETS / "durian-two-projects-hero.png", 0, 125, W, H - 125)
    c.saveState()
    c.setFillColor(DEEP)
    c.setFillAlpha(0.90)
    c.rect(0, 0, W, 205, fill=1, stroke=0)
    c.restoreState()
    c.setFillColor(CYAN)
    c.rect(38, 184, 64, 4, fill=1, stroke=0)
    ptext(c, "BẢN THẢO ĐỀ XUẤT", 38, 175, 300, style(9, 11, colors.HexColor("#9ADBD7"), True))
    ptext(c, "CHƯƠNG TRÌNH AI CHO SẦU RIÊNG", 38, 150, 650, style(29, 32, WHITE, True))
    ptext(c, "Định danh dấu vân bề mặt  |  Dự báo chất lượng quả và múi", 38, 112, 700, style(14, 18, colors.HexColor("#DDEDE4"), True))
    ptext(c, "Một quy trình lấy mẫu chung, hai sản phẩm dữ liệu độc lập và có thể kiểm chứng.", 38, 82, 650, style(10, 14, colors.HexColor("#B7CCC4")))
    chip(c, "MỘT QUẢ - MỘT ID", 38, 35, 135, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    chip(c, "THỬ NGHIỆM TRƯỚC", 182, 35, 145, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    chip(c, "ĐO ĐƯỢC MỚI MỞ RỘNG", 336, 35, 177, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    ptext(c, "04.09.2026", W - 130, 46, 92, style(8.5, 10, colors.HexColor("#B7CCC4"), True, TA_CENTER))
    c.showPage()


def executive_summary(c):
    section_header(c, 2, "01 / Tóm tắt", "Hai bài toán, một tài sản dữ liệu chung",
                   "Mục tiêu là tạo bằng chứng có thể đo, không bắt đầu bằng ứng dụng hay mô hình phức tạp.")
    rounded(c, 38, 355, 242, 132, fill=WHITE)
    ptext(c, "BÀI TOÁN THỊ TRƯỜNG", 54, 468, 210, style(8, 10, GREEN, True))
    bullets(c, [
        "Nguồn gốc từng quả khó kiểm chứng sau khi rời vườn hoặc điểm đóng gói.",
        "Grade thương mại còn phụ thuộc kinh nghiệm và thiếu dữ liệu đối chiếu sau khi bổ.",
        "Cùng một lần quét trước khi bổ có thể phục vụ cả hai bài toán.",
    ], 52, 445, 212, style(9, 12, INK), 4)

    rounded(c, 298, 355, 242, 132, fill=colors.HexColor("#E3F0E7"), stroke=colors.HexColor("#A8C8B8"))
    ptext(c, "DỰ ÁN 1  /  FINGERPRINT", 314, 468, 210, style(8, 10, GREEN, True))
    ptext(c, "Xác minh đúng quả", 314, 446, 210, style(16, 19, INK, True))
    ptext(c, "So khớp gai, hõm, khe và vân vỏ giữa hồ sơ đăng ký với ảnh/quét độc lập.", 314, 420, 205, style(9, 12, INK))
    chip(c, "ĐÚNG  /  CHƯA CHẮC  /  SAI", 314, 370, 194, GREEN, WHITE)

    rounded(c, 558, 355, 246, 132, fill=colors.HexColor("#FFF3D9"), stroke=colors.HexColor("#E6C77B"))
    ptext(c, "DỰ ÁN 2  /  QUALITY", 574, 468, 214, style(8, 10, colors.HexColor("#956B19"), True))
    ptext(c, "Dự báo chất lượng", 574, 446, 214, style(16, 19, INK, True))
    ptext(c, "Ước lượng số múi, múi đầy/lép, tỷ lệ cơm ăn được và độ tin cậy trước khi bổ.", 574, 420, 210, style(9, 12, INK))
    chip(c, "DỰ BÁO + KHOẢNG TIN CẬY", 574, 370, 194, GOLD, WHITE)

    ptext(c, "SỰ THẬT KỸ THUẬT HIỆN TẠI", 38, 325, 760, style(10, 12, INK, True))
    data = [
        ["Hạng mục", "Đã có", "Chưa có / cần chứng minh"],
        ["Thu nhận dữ liệu", "Video RGB-D, IMU, pose; quy trình 2 camera; mã mẫu", "Pilot đồng nhất không có chữ viết trên vỏ"],
        ["Fingerprint", "Unwrap RGB, view bank, SIFT và kiểm tra hình học", "Ngưỡng thật/giả trên nhiều quả và ảnh độc lập"],
        ["Chất lượng", "403 ảnh hộc, 8 trang sổ; schema cân và số hộc", "Duyệt nhãn; Brix/chất khô và baseline dự báo"],
        ["3D / LiDAR", "Có tín hiệu dáng thô và relief", "Chưa đủ ổn định làm ground truth từng gai"],
    ]
    simple_table(c, data, 38, 305, [120, 275, 351], font_size=8.4)
    rounded(c, 38, 48, 766, 42, fill=DEEP, stroke=DEEP)
    ptext(c, "Khuyến nghị: dùng dữ liệu hiện có để smoke test và audit leakage ngay; pilot sạch 60 quả được thực hiện ở đợt lấy mẫu sau, trong đó 30 quả có query fingerprint độc lập.", 55, 76, 730, style(10, 13, WHITE, True, TA_CENTER))
    c.showPage()


def shared_program(c):
    section_header(c, 3, "02 / Kiến trúc chương trình", "Một vòng đời dữ liệu, hai nhánh giá trị",
                   "Dữ liệu gốc được thu một lần; hai nhánh có nhãn, metric và quyết định triển khai riêng.")
    image_cover(c, ASSETS / "scanner-frame.jpg", 38, 275, 230, 210)
    rounded(c, 38, 235, 230, 32, fill=DEEP, stroke=DEEP, radius=0)
    ptext(c, "Ảnh thật từ bộ quét thử nghiệm", 48, 257, 210, style(9, 11, WHITE, True, TA_CENTER))
    ptext(c, "ĐẦU VÀO CHUNG", 38, 218, 230, style(9, 11, GREEN, True))
    bullets(c, [
        "fruit_id duy nhất; QR chỉ để quản lý",
        "2 camera, ánh sáng khóa, mâm xoay",
        "cân nặng, kích thước, mốc hiệu chuẩn",
        "sau khi bổ: ảnh và nhãn từng múi",
    ], 42, 198, 222, style(8.8, 11.5, INK), 3)

    node(c, 300, 375, 155, 82, "1. Thu nhận", "Video, depth, timestamp, cân nặng, metadata", colors.HexColor("#E5F1E9"))
    node(c, 500, 375, 155, 82, "2. Chuẩn hóa", "Đồng bộ, mask quả, QC, chọn view", colors.HexColor("#E5F1E9"))
    arrow(c, 455, 416, 500, 416)

    node(c, 685, 395, 119, 62, "Kho dữ liệu", "File + manifest có phiên bản", colors.HexColor("#EEF3EF"))
    arrow(c, 655, 416, 685, 426)

    node(c, 300, 235, 155, 92, "3A. Fingerprint", "View bank, local features, truy hồi và kiểm tra hình học", colors.HexColor("#DDF0E8"), GREEN)
    node(c, 500, 235, 155, 92, "Kết quả", "Đúng quả / chưa chắc / sai quả", colors.HexColor("#DDF0E8"), GREEN)
    arrow(c, 455, 281, 500, 281)

    node(c, 300, 95, 155, 92, "3B. Chất lượng", "Feature ảnh + dáng + cân nặng; học có giám sát", colors.HexColor("#FFF2D7"), GOLD)
    node(c, 500, 95, 155, 92, "Kết quả", "Số múi, độ đầy, tỷ lệ cơm + độ tin cậy", colors.HexColor("#FFF2D7"), GOLD)
    arrow(c, 455, 141, 500, 141, GOLD)

    node(c, 685, 95, 119, 92, "Ground truth", "Bổ quả, chụp từng hộc, cân vỏ/cơm/hạt", colors.HexColor("#F9E9C5"), GOLD)
    arrow(c, 685, 141, 655, 141, GOLD)
    arrow(c, 577, 375, 377, 327, GREEN)
    arrow(c, 577, 375, 377, 187, GOLD)

    rounded(c, 685, 235, 119, 92, fill=WHITE)
    ptext(c, "NGUYÊN TẮC", 697, 307, 95, style(8, 10, GREEN, True, TA_CENTER))
    ptext(c, "Cùng nguồn dữ liệu, nhưng không dùng kết quả của dự án này để che điểm yếu của dự án kia.", 697, 286, 95, style(8, 10.5, INK, False, TA_CENTER))
    c.showPage()


def operating_modes(c):
    section_header(c, 4, "03 / Bối cảnh vận hành", "Bốn luồng sử dụng của cùng nền tảng",
                   "Hai luồng ở dây chuyền và hai luồng trên điện thoại; nhận dạng và đánh giá chất lượng không phụ thuộc lẫn nhau.")
    modes = [
        ("1", "Đăng ký tại dây chuyền", "Quét 360 độ từng quả", "Tạo fruit_id, hồ sơ fingerprint, nguồn gốc và sự kiện nhập kho.", GREEN),
        ("2", "Phân loại tại dây chuyền", "Quét mọi quả đi qua", "Ước lượng số múi, độ đầy, tỷ lệ cơm, độ chín; chuyển làn hoặc REVIEW.", GOLD),
        ("3", "Xác minh ngoài hiện trường", "Quét quả đã đăng ký", "Fingerprint tìm fruit_id rồi hiển thị vườn, lô/cây, địa lý và khí hậu có nguồn.", CYAN),
        ("4", "Đánh giá quả bất kỳ", "Không cần có fingerprint", "Điện thoại dự báo số múi, chất lượng và quả đã chín chưa, kèm độ tin cậy.", colors.HexColor("#7A5DA8")),
    ]
    positions = [(38, 290), (428, 290), (38, 82), (428, 82)]
    for (number, title, subtitle, detail, accent), (x, y) in zip(modes, positions):
        rounded(c, x, y, 376, 174, fill=WHITE)
        c.setFillColor(accent)
        c.circle(x + 37, y + 137, 21, fill=1, stroke=0)
        ptext(c, number, x + 20, y + 148, 34, style(15, 18, WHITE, True, TA_CENTER))
        ptext(c, escape(title), x + 72, y + 151, 282, style(14, 17, INK, True))
        ptext(c, escape(subtitle), x + 72, y + 126, 282, style(9, 11, accent, True))
        c.setStrokeColor(LINE)
        c.line(x + 20, y + 103, x + 356, y + 103)
        ptext(c, escape(detail), x + 24, y + 84, 328, style(9.2, 12.5, INK, False, TA_CENTER))
        chip(c, "FINGERPRINT" if number in ("1", "3") else "QUALITY", x + 126, y + 17, 124, accent, WHITE)

    rounded(c, 38, 48, 766, 24, fill=DEEP, stroke=DEEP)
    ptext(c, "Luồng 4 hoạt động với quả chưa từng có trong kho; nếu ảnh nằm ngoài miền dữ liệu hoặc thiếu góc nhìn, hệ thống phải trả CHƯA ĐỦ DỮ LIỆU.", 48, 65, 746, style(8.2, 10, WHITE, True, TA_CENTER))
    c.showPage()


def industrial_cell(c):
    section_header(c, 5, "04 / Dây chuyền công nghiệp", "Cell quét sầu riêng gắn vào dây chuyền",
                   "Bản đầu dùng cell dừng-ngắn và con lăn xoay quả; throughput được đo trong pilot, không hứa trước bằng mô phỏng.")
    image_cover(c, ASSETS / "industrial-durian-scan-cell.png", 38, 227, 475, 260)
    ptext(c, "Minh họa cell công nghiệp - camera cố định, ánh sáng tản và con lăn xoay", 45, 216, 460, style(7.7, 9, MUTED, False, TA_CENTER))

    rounded(c, 536, 352, 268, 135, fill=WHITE)
    ptext(c, "KHUNG XỬ LÝ TỐI THIỂU", 552, 468, 236, style(8.5, 10, GREEN, True))
    bullets(c, [
        "cảm biến phát hiện một quả vào cell",
        "giữ quả ổn định và xoay đủ góc nhìn",
        "2-3 camera RGB + đèn tản; depth là tùy chọn",
        "edge computer chạy QC và preview",
        "che chắn cơ khí, nút dừng và vệ sinh dễ",
    ], 550, 445, 240, style(8.3, 10.4, INK), 2)

    rounded(c, 536, 227, 268, 108, fill=DEEP, stroke=DEEP)
    ptext(c, "KẾT QUẢ TRONG MỘT CHU KỲ", 552, 316, 236, style(8.5, 10, colors.HexColor("#9ADBD7"), True))
    bullets(c, [
        "fruit_id/fingerprint nếu đăng ký",
        "số múi, chất lượng, độ chín dự kiến",
        "PASS / REVIEW / REJECT và lý do QC",
        "JSON/CSV/webhook cho PLC, MES hoặc WMS",
    ], 550, 294, 240, style(8.2, 10.2, WHITE), 2, GOLD)

    ptext(c, "LUỒNG TRÊN DÂY CHUYỀN", 38, 180, 766, style(9, 11, GREEN, True))
    flow = [
        (38, "1. Nhận quả", "photoeye / trigger"),
        (196, "2. Xoay + quét", "multi-view RGB"),
        (354, "3. QC", "blur, sáng, coverage"),
        (512, "4. Suy luận", "ID và/hoặc quality"),
        (670, "5. Hành động", "ghi hồ sơ / chuyển làn"),
    ]
    for index, (x, title, detail) in enumerate(flow):
        node(c, x, 95, 134, 67, title, detail, WHITE, GREEN if index < 3 else GOLD)
        if index < len(flow) - 1:
            arrow(c, x + 134, 128, x + 158, 128, CYAN)
    ptext(c, "Khuyến nghị: bắt đầu bằng một cell xoay chậm; chỉ chuyển sang tunnel nhiều camera khi throughput đo được thật sự là nút thắt.", 38, 79, 766, style(7.5, 9, MUTED, False, TA_CENTER))
    c.showPage()


def field_phone(c):
    section_header(c, 6, "05 / Điện thoại hiện trường", "Quét, hướng dẫn và visualize kết quả ngay",
                   "Ứng dụng ưu tiên phản hồi chất lượng ảnh tại máy; nhận dạng và suy luận đầy đủ có thể chạy qua server hoặc đồng bộ sau.")
    image_cover(c, ASSETS / "field-phone-durian-scan.png", 38, 215, 400, 282)
    ptext(c, "Minh họa quét quả đang treo tại vườn", 46, 204, 384, style(7.7, 9, MUTED, False, TA_CENTER))

    rounded(c, 460, 405, 344, 92, fill=WHITE)
    ptext(c, "TRONG KHI QUÉT", 476, 478, 312, style(8.5, 10, GREEN, True))
    ptext(c, "Overlay điểm bám + vòng coverage  |  cảnh báo mờ, thiếu sáng, quá gần  |  gợi ý xoay sang vùng còn thiếu", 476, 454, 312, style(9.1, 12, INK, True, TA_CENTER))

    rounded(c, 460, 310, 344, 80, fill=colors.HexColor("#E3F0E7"), stroke=colors.HexColor("#A8C8B8"))
    ptext(c, "A / TÌM THẤY FINGERPRINT", 476, 371, 312, style(8.5, 10, GREEN, True))
    ptext(c, "Đúng quả? + độ tin cậy  |  vườn/lô/cây  |  vị trí  |  thời tiết và khí hậu theo nguồn", 476, 347, 312, style(9, 12, INK, True, TA_CENTER))

    rounded(c, 460, 215, 344, 80, fill=colors.HexColor("#F0EAF8"), stroke=colors.HexColor("#C7B6DF"))
    ptext(c, "B / QUẢ BẤT KỲ - KHÔNG CẦN ĐĂNG KÝ", 476, 276, 312, style(8.5, 10, colors.HexColor("#694B94"), True))
    ptext(c, "Số múi dự kiến  |  đầy/lép  |  tỷ lệ cơm  |  đã chín chưa  |  nguy cơ lỗi  |  độ tin cậy", 476, 252, 312, style(9, 12, INK, True, TA_CENTER))

    ptext(c, "TỪ FINGERPRINT ĐẾN HỒ SƠ NGUỒN GỐC", 38, 174, 766, style(9, 11, GREEN, True))
    trace = [
        (38, 126, "Fingerprint", "bằng chứng hình học"),
        (190, 126, "fruit_id", "khóa truy xuất"),
        (342, 126, "Hồ sơ đăng ký", "vườn, cây, lô, ngày"),
        (494, 126, "Địa lý + thời gian", "tọa độ, thời điểm"),
        (646, 126, "Khí hậu có nguồn", "mưa, nhiệt, ẩm"),
    ]
    for index, (x, y, title, detail) in enumerate(trace):
        node(c, x, 86, 128, 60, title, detail, WHITE, CYAN if index < 2 else GREEN)
        if index < len(trace) - 1:
            arrow(c, x + 128, 116, x + 152, 116, CYAN)
    ptext(c, "Fingerprint chỉ trả về fruit_id. Thông tin vườn/địa lý đến từ hồ sơ đăng ký; khí hậu là dữ liệu enrich theo tọa độ + thời gian, phải hiển thị nguồn và thời điểm cập nhật.", 38, 70, 766, style(7.8, 9.5, MUTED, True, TA_CENTER))
    c.showPage()


def fingerprint_project(c):
    section_header(c, 7, "06 / Dự án 1", "Fingerprint - xác minh đúng từng quả",
                   "Dấu vân chính là cấu trúc tự nhiên của vỏ; QR giúp tìm hồ sơ nhưng không phải bằng chứng nhận dạng.")
    image_cover(c, ASSETS / "durian-fingerprint-concept.png", 38, 95, 275, 392, anchor_y=0.45)
    ptext(c, "Minh họa khái niệm - đường cyan biểu diễn đặc trưng bề mặt", 46, 84, 260, style(7.5, 9, MUTED, False, TA_CENTER))

    x = 338
    ptext(c, "Dấu hiệu cần lưu", x, 472, 220, style(10, 12, GREEN, True))
    bullets(c, [
        "gai nổi bật và quan hệ hình học giữa các cụm gai",
        "hõm, chân gai, khe múi và đường nứt tự nhiên",
        "mảng màu và texture cục bộ",
        "dáng thô, cuống, đáy và vùng bị che",
    ], x + 2, 448, 220, style(9, 12, INK), 4)

    ptext(c, "Luồng đăng ký", 585, 472, 205, style(10, 12, GREEN, True))
    node(c, 585, 397, 205, 48, "Quét 360 độ", "Hai camera, view gốc sắc nét", colors.HexColor("#E5F1E9"))
    node(c, 585, 329, 205, 48, "Tạo hồ sơ", "36 view/camera + local descriptors", colors.HexColor("#E5F1E9"))
    node(c, 585, 261, 205, 48, "Lập chỉ mục", "Coarse vector + đặc trưng hình học", colors.HexColor("#E5F1E9"))
    arrow(c, 688, 397, 688, 377)
    arrow(c, 688, 329, 688, 309)

    rounded(c, 338, 98, 220, 150, fill=WHITE)
    ptext(c, "STACK PROTOTYPE HIỆN CÓ", 354, 228, 188, style(8, 10, GREEN, True))
    bullets(c, [
        "SIFT/RootSIFT trong mask quả",
        "histogram 64 visual words để lấy ứng viên",
        "PCA 32 chiều để nén descriptor",
        "fundamental matrix + homography để xác minh",
        "non_dark_inliers giảm ảnh hưởng nét bút đen",
    ], 352, 207, 194, style(8.4, 10.5, INK), 3)

    rounded(c, 585, 98, 205, 136, fill=DEEP, stroke=DEEP)
    ptext(c, "LUỒNG NGƯỜI MUA", 601, 216, 173, style(8, 10, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Ảnh/quét 10-20 giây", 601, 193, 173, style(11, 14, WHITE, True, TA_CENTER))
    ptext(c, "↓", 601, 169, 173, style(15, 16, colors.HexColor("#9ADBD7"), True, TA_CENTER))
    ptext(c, "Tìm view gần nhất + kiểm tra hình học", 601, 150, 173, style(9, 12, WHITE, False, TA_CENTER))
    ptext(c, "ĐÚNG  /  CHƯA CHẮC  /  SAI", 601, 116, 173, style(8.5, 10, colors.HexColor("#F0D08A"), True, TA_CENTER))
    c.showPage()


def fingerprint_evidence(c):
    section_header(c, 8, "07 / Hiện trạng kỹ thuật", "Fingerprint: có tín hiệu, chưa đủ để tuyên bố",
                   "Các artefact dưới đây là kết quả thật trong repo; chúng cho biết nên thử tiếp ở đâu và phải dừng kỳ vọng nào.")
    rounded(c, 38, 306, 365, 180, fill=WHITE)
    image_contain(c, ROOT / "test_video/processed/video-body-unwrap/body-texture-map.png", 50, 348, 341, 112)
    ptext(c, "RGB body unwrap 360 độ", 54, 333, 335, style(10, 12, INK, True, TA_CENTER))
    ptext(c, "43/48 frame | map 1259 x 353 px | coverage 100% | chỉ phần thân giữa", 54, 315, 335, style(7.8, 9.5, MUTED, False, TA_CENTER))

    rounded(c, 421, 306, 383, 180, fill=WHITE)
    image_contain(c, ASSETS / "retrieval-pairs.png", 433, 335, 359, 130)
    ptext(c, "Ảnh query và view ứng viên", 437, 326, 351, style(10, 12, INK, True, TA_CENTER))
    ptext(c, "Prototype tìm được vùng tương ứng, nhưng mới có một quả và bị nhiễu bởi chữ viết đen.", 437, 311, 351, style(7.8, 9.5, MUTED, False, TA_CENTER))

    rounded(c, 38, 78, 245, 198, fill=WHITE)
    ptext(c, "TÍN HIỆU TÍCH CỰC", 54, 256, 213, style(8.5, 10, GREEN, True))
    bullets(c, [
        "Cylindrical unwrap giữ RGB sắc hơn cách trộn nhiều frame.",
        "View bank + kiểm tra hình học phù hợp với ảnh chụp một vùng.",
        "Ảnh held-out cùng điều kiện lệch góc 5 độ trong thử nghiệm atlas.",
    ], 52, 232, 215, style(8.6, 11, INK), 5)

    rounded(c, 298, 78, 245, 198, fill=colors.HexColor("#FFF2EA"), stroke=colors.HexColor("#E9B6A7"))
    ptext(c, "ĐIỂM CHƯA ĐƯỢC CHỨNG MINH", 314, 256, 213, style(8.5, 10, RED, True))
    bullets(c, [
        "Chưa có phân bố genuine/impostor trên nhiều quả.",
        "NCC ảnh người mua chỉ 0,0352-0,0738; chưa có ngưỡng đúng/sai.",
        "Nét bút đen và bối cảnh có thể làm rò rỉ danh tính.",
        "Full 360 độ vẫn chịu parallax, seam và vùng bị che.",
    ], 312, 232, 215, style(8.6, 11, INK), 4)

    rounded(c, 558, 78, 246, 198, fill=DEEP, stroke=DEEP)
    ptext(c, "KẾT LUẬN HIỆN TẠI", 574, 256, 214, style(8.5, 10, colors.HexColor("#9ADBD7"), True))
    ptext(c, "GO cho pilot có đối chứng", 574, 226, 214, style(16, 19, WHITE, True, TA_CENTER))
    ptext(c, "NOT GO cho tuyên bố sản phẩm", 574, 194, 214, style(11, 14, colors.HexColor("#F0D08A"), True, TA_CENTER))
    ptext(c, "LiDAR giữ vai trò phụ trợ dáng thô; không coi depth 256 x 192 là ground truth từng gai.", 578, 160, 206, style(8.6, 11.5, WHITE, False, TA_CENTER))
    ptext(c, "Centerline relief P99: 4,15 mm | fusion band: 1,23 mm", 578, 112, 206, style(7.7, 9.5, colors.HexColor("#B7CCC4"), True, TA_CENTER))
    c.showPage()


def fingerprint_experiment(c):
    section_header(c, 9, "08 / Thiết kế thí nghiệm", "Pilot Fingerprint tối thiểu có đối chứng",
                   "Mục tiêu: xác định ảnh độc lập có thể nhận đúng một quả trong kho và từ chối quả khác hay không.")
    image_cover(c, ASSETS / "current-pilot-scans.jpg", 38, 285, 262, 200)
    ptext(c, "Dữ liệu hiện có chỉ dùng smoke test vì có chữ viết trên vỏ", 44, 274, 250, style(7.6, 9, MUTED, True, TA_CENTER))

    data = [
        ["Thiết kế đề xuất", "Quy định"],
        ["Đối tượng", "30 quả nguyên vẹn, không viết mã lên vỏ; đa dạng hình dáng và màu"],
        ["Enrollment", "2 camera đồng bộ; 2 vòng quay; giữ view RGB gốc; QC trước khi nhập kho"],
        ["Positive query", "6 ảnh/quả, 2 người chụp, 3 điều kiện; chụp độc lập sau 24-72 giờ hoặc vận chuyển"],
        ["Negative control", "Mỗi query được so với toàn bộ 29 quả còn lại"],
        ["Khóa tham số", "20 quả để chỉnh; khóa thuật toán/ngưỡng; 10 quả mới để test mù"],
    ]
    simple_table(c, data, 325, 485, [118, 361], font_size=8.3, row_padding=6)

    ptext(c, "METRIC CHÍNH", 38, 244, 235, style(9, 11, GREEN, True))
    rounded(c, 38, 90, 235, 138, fill=WHITE)
    bullets(c, [
        "Top-1 identification accuracy",
        "TAR tại empirical FAR <= 1%",
        "tỷ lệ trả về 'chưa chắc'",
        "genuine/impostor score theo từng quả",
        "bootstrap confidence interval theo fruit_id",
    ], 52, 207, 207, style(8.5, 10.7, INK), 3)

    ptext(c, "CHỐNG RÒ RỈ DỮ LIỆU", 298, 244, 235, style(9, 11, GREEN, True))
    rounded(c, 298, 90, 235, 138, fill=WHITE)
    bullets(c, [
        "không chữ, tem hoặc QR trong vùng vỏ",
        "query khác buổi, người chụp và khoảng cách",
        "không tách train/test theo frame",
        "threshold chỉ được chốt trên tập chỉnh",
        "review false match bằng overlay hình học",
    ], 312, 207, 207, style(8.5, 10.7, INK), 3)

    ptext(c, "CỔNG QUYẾT ĐỊNH PILOT", 558, 244, 246, style(9, 11, GREEN, True))
    rounded(c, 558, 90, 246, 138, fill=DEEP, stroke=DEEP)
    ptext(c, "GO", 574, 207, 45, style(9, 11, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Top-1 >= 90% và TAR >= 85% tại FAR <= 1%", 620, 207, 165, style(8.4, 10.5, WHITE))
    ptext(c, "LẶP", 574, 167, 45, style(9, 11, colors.HexColor("#F0D08A"), True))
    ptext(c, "có separation nhưng lỗi tập trung theo góc/điều kiện", 620, 167, 165, style(8.4, 10.5, WHITE))
    ptext(c, "DỪNG", 574, 125, 45, style(9, 11, colors.HexColor("#F1A99C"), True))
    ptext(c, "không hơn chance sau khi bỏ marker và nền", 620, 125, 165, style(8.4, 10.5, WHITE))
    ptext(c, "Các ngưỡng trên là đề xuất để quản trị pilot, chưa phải SLA sản phẩm.", 558, 76, 246, style(7.5, 9, MUTED, False, TA_CENTER))
    c.showPage()


def quality_project(c):
    section_header(c, 10, "09 / Dự án 2", "Dự báo chất lượng quả và từng múi",
                   "Dự báo không phá quả; ground truth bắt buộc đến từ mẫu được bổ, chụp và cân có kiểm soát.")
    image_cover(c, ASSETS / "durian-quality-concept.png", 529, 95, 275, 392, anchor_y=0.45)
    ptext(c, "Minh họa khái niệm - không phải kết quả mô hình", 537, 84, 260, style(7.5, 9, MUTED, False, TA_CENTER))

    ptext(c, "ĐẦU RA THEO THỨ TỰ ƯU TIÊN", 38, 470, 455, style(9, 11, colors.HexColor("#956B19"), True))
    rows = [
        ("1", "Số múi / số hộc", "classification + MAE", "MVP"),
        ("2", "Tỷ lệ cơm ăn được", "regression", "MVP"),
        ("3", "Múi đầy / vừa / lép / hư", "multi-label / ordinal", "Pilot"),
        ("4", "Độ chín, °Brix, chất khô", "regression + class.", "Mở rộng"),
    ]
    y = 440
    for number, title, task, phase in rows:
        rounded(c, 38, y - 52, 455, 46, fill=WHITE)
        c.setFillColor(GOLD)
        c.circle(62, y - 29, 13, fill=1, stroke=0)
        ptext(c, number, 51, y - 22, 22, style(10, 12, WHITE, True, TA_CENTER))
        ptext(c, escape(title), 85, y - 17, 205, style(10, 12, INK, True))
        ptext(c, escape(task), 294, y - 17, 115, style(8.2, 10, MUTED))
        chip(c, phase.upper(), 414, y - 40, 67, colors.HexColor("#F5E4BA"), colors.HexColor("#956B19"))
        y -= 57

    ptext(c, "ĐẦU VÀO", 38, 190, 212, style(9, 11, colors.HexColor("#956B19"), True))
    rounded(c, 38, 92, 212, 84, fill=colors.HexColor("#FFF3D9"), stroke=colors.HexColor("#E6C77B"))
    bullets(c, [
        "RGB nhiều góc và texture vỏ",
        "dáng thô/depth phụ trợ",
        "khối lượng và kích thước",
        "nguồn/giống/ngày thu hoạch nếu có",
    ], 50, 157, 188, style(8.2, 10.2, INK), 2)

    ptext(c, "GROUND TRUTH", 274, 190, 219, style(9, 11, colors.HexColor("#956B19"), True))
    rounded(c, 274, 92, 219, 84, fill=colors.HexColor("#FFF3D9"), stroke=colors.HexColor("#E6C77B"))
    bullets(c, [
        "segment_count và nhãn từng hộc",
        "whole/shell/flesh/seed weight",
        "°Brix 3 lần + chất khô 2 mẫu lặp",
        "ảnh kiểm chứng; grade thương mại lưu riêng",
    ], 286, 157, 195, style(8.2, 10.2, INK), 2)
    c.showPage()


def quality_experiment(c):
    section_header(c, 11, "10 / Thiết kế thí nghiệm", "Pilot Quality - thu nhãn trước, model sau",
                   "Mục tiêu: kiểm tra tín hiệu dự báo ngoài vỏ có vượt baseline đơn giản trên fruit_id chưa từng thấy hay không.")
    data = [
        ["Khối", "Thiết kế đề xuất", "Lý do"],
        ["Mẫu", "60 quả được bổ; ít nhất 3 nguồn/lô; có dải grade và độ chín", "Đủ chạy baseline, chưa đủ tuyên bố production"],
        ["Trước khi bổ", "Scan A/B, cân cả quả, đo kích thước, ghi grade của chuyên gia", "Giữ dữ liệu không phá quả"],
        ["Sau khi scan", "Đánh dấu khe số 0 bằng mực thực phẩm rồi mới bổ", "Giữ liên kết vị trí vỏ - hộc, không làm rò fingerprint"],
        ["Sau khi bổ", "Ảnh + cân + nhãn hộc; Brix 3 lần; chất khô 2 mẫu theo SOP", "Ground truth có thể kiểm tra lại"],
        ["Split", "Theo fruit_id và theo nguồn/ngày; tuyệt đối không split theo frame", "Chặn leakage và đo khả năng tổng quát hóa"],
    ]
    simple_table(c, data, 38, 480, [80, 386, 300], font_size=8.1, row_padding=5.5)

    ptext(c, "MODEL LADDER", 38, 211, 238, style(9, 11, colors.HexColor("#956B19"), True))
    rounded(c, 38, 70, 238, 126, fill=WHITE)
    bullets(c, [
        "B0: mean/majority theo tập train",
        "B1: cân nặng + kích thước + màu cơ bản",
        "B2: embedding ảnh, gộp nhiều view",
        "B3: multi-task model chỉ khi dữ liệu đủ lớn",
    ], 52, 177, 210, style(8.5, 10.8, INK), 4)

    ptext(c, "METRIC", 301, 211, 238, style(9, 11, colors.HexColor("#956B19"), True))
    rounded(c, 301, 70, 238, 126, fill=WHITE)
    bullets(c, [
        "số múi: exact accuracy + MAE",
        "tỷ lệ cơm: MAE điểm phần trăm + R²",
        "độ đầy: macro-F1 theo hộc",
        "Brix/chất khô: MAE + R²",
        "confidence interval bootstrap theo quả",
    ], 315, 177, 210, style(8.1, 9.8, INK), 2)

    ptext(c, "CỔNG PILOT ĐỀ XUẤT", 564, 211, 240, style(9, 11, colors.HexColor("#956B19"), True))
    rounded(c, 564, 70, 240, 126, fill=DEEP, stroke=DEEP)
    bullets(c, [
        "số múi exact accuracy >= 75%",
        "tỷ lệ cơm MAE <= 8 điểm phần trăm",
        "múi đầy/lép macro-F1 >= 0,60",
        "đồng thời phải vượt baseline B0/B1",
    ], 578, 177, 212, style(8.4, 10.5, WHITE), 3, GOLD)
    ptext(c, "Ngưỡng dùng quản trị feasibility, sẽ hiệu chỉnh sau pilot.", 564, 56, 240, style(7.4, 9, MUTED, False, TA_CENTER))
    c.showPage()


def data_governance(c):
    section_header(c, 12, "11 / Dữ liệu", "Schema chung và kiểm soát chất lượng",
                   "Excel/CSV và manifest tiếp tục là nguồn sự thật cho tới khi quy trình lấy mẫu ổn định.")
    data = [
        ["Đối tượng", "Khóa chính", "Nội dung tối thiểu"],
        ["Quả", "fruit_id", "farm_id, tree_id, fruit_seq, nguồn, giống, ngày"],
        ["Cây", "tree_id + ngày", "GPS; app estimate; chiều cao và D1/D2 đo đối chứng; trạng thái"],
        ["Lượt quét", "sample_id", "pass, camera_id, thời gian, file video, calibration, QC"],
        ["View", "sample_id + angle", "frame index, mask, sharpness, feature count, coverage"],
        ["Ground truth", "fruit_id + segment", "segment_count, ảnh hộc, cân nặng, Brix, chất khô"],
        ["Artefact", "pipeline_version", "view bank, atlas, feature, model output, metric"],
    ]
    simple_table(c, data, 38, 482, [110, 150, 506], font_size=8.5, row_padding=6)

    ptext(c, "QUY TẮC KHÔNG THỎA HIỆP", 38, 240, 766, style(9, 11, GREEN, True))
    cards = [
        ("Không leakage", "Một fruit_id chỉ nằm trong một split. Không dùng chữ viết, QR hay nền làm tín hiệu."),
        ("Ground truth truy vết được", "Mỗi số cân và nhãn hộc phải liên kết tới ảnh/video kiểm chứng."),
        ("Version mọi thứ", "Protocol, manifest, pipeline, vocabulary, model và threshold đều có phiên bản."),
        ("Có quyền từ chối", "QC lỗi hoặc model thiếu bằng chứng phải trả REVIEW/CHƯA CHẮC."),
    ]
    for index, (title, detail) in enumerate(cards):
        x = 38 + index * 194
        rounded(c, x, 95, 178, 126, fill=WHITE)
        c.setFillColor(GREEN if index != 1 else GOLD)
        c.circle(x + 22, 195, 7, fill=1, stroke=0)
        ptext(c, escape(title), x + 16, 177, 146, style(10, 12, INK, True, TA_CENTER))
        ptext(c, escape(detail), x + 16, 149, 146, style(8.2, 10.8, MUTED, False, TA_CENTER))
    c.showPage()


def roadmap(c):
    section_header(c, 13, "12 / Hướng triển khai", "Từ pilot đến sản phẩm theo cổng quyết định",
                   "Không mua thêm phần cứng hoặc xây platform lớn trước khi metric chứng minh giá trị.")
    phases = [
        ("0", "2 TUẦN", "Khóa protocol", ["schema + mã mẫu", "rig + đối chứng đo cây", "benchmark dữ liệu cũ"], GREEN),
        ("1", "4-6 TUẦN", "Pilot đợt sau", ["30 quả có query độc lập", "60 quả: Brix + chất khô", "báo cáo blind test"], CYAN),
        ("2", "8-12 TUẦN", "Mở rộng dữ liệu", ["300-500 quả", "nhiều vườn/mùa/thiết bị", "khóa baseline v2"], GOLD),
        ("3", "3-6 THÁNG", "Tích hợp sản phẩm", ["API đăng ký/xác minh", "trạm chấm chất lượng", "monitor drift + review"], colors.HexColor("#7A5DA8")),
    ]
    xs = [38, 234, 430, 626]
    for index, ((number, duration, title, items, accent), x) in enumerate(zip(phases, xs)):
        rounded(c, x, 170, 178, 295, fill=WHITE)
        c.setFillColor(accent)
        c.roundRect(x, 415, 178, 50, 10, fill=1, stroke=0)
        ptext(c, f"PHA {number}", x + 14, 449, 55, style(8.5, 10, WHITE, True))
        ptext(c, duration, x + 72, 449, 90, style(8.5, 10, WHITE, True, TA_CENTER))
        ptext(c, escape(title), x + 14, 393, 150, style(14, 17, INK, True, TA_CENTER))
        bullets(c, [escape(item) for item in items], x + 16, 352, 146, style(8.6, 11, INK), 5, accent)
        ptext(c, [
            "Deliverable: protocol v1 + dữ liệu dry-run sạch.",
            "Deliverable: score distributions, metric và quyết định GO/LẶP/DỪNG.",
            "Deliverable: model card, error taxonomy và estimate vận hành.",
            "Deliverable: quy trình có giám sát, audit và rollback.",
        ][index], x + 15, 243, 148, style(8, 10.5, MUTED, False, TA_CENTER))
        if index < len(phases) - 1:
            arrow(c, x + 178, 317, x + 196, 317, accent)

    rounded(c, 38, 78, 766, 64, fill=DEEP, stroke=DEEP)
    ptext(c, "Điều kiện chuyển pha", 54, 124, 145, style(9, 11, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Chỉ chuyển khi dữ liệu đạt QC, metric blind test đạt cổng và lỗi đã có taxonomy. Nếu chưa đạt, sửa protocol hoặc dừng nhánh - không bù bằng thêm UI.", 190, 124, 592, style(9.2, 12.5, WHITE, True))
    c.showPage()


def minimal_architecture(c):
    section_header(c, 14, "13 / Vận hành", "Kiến trúc và nguồn lực tối thiểu",
                   "Giữ hệ thống đơn giản: file gốc bất biến, manifest có version, batch có thể chạy lại và một lớp review của con người.")
    nodes = [
        (38, "Capture", "điện thoại / scan cell\nvideo + metadata"),
        (198, "Storage", "Thư mục chuẩn\nfile gốc bất biến"),
        (358, "Manifest", "CSV/XLSX\nfruit_id + QC"),
        (518, "Batch", "view bank / feature\nmodel + report"),
        (678, "Review/API", "duyệt lỗi\nkết quả 3 trạng thái"),
    ]
    for index, (x, title, detail) in enumerate(nodes):
        node(c, x, 350, 126, 84, title, detail, WHITE, GREEN if index < 4 else CYAN)
        if index < len(nodes) - 1:
            arrow(c, x + 126, 392, x + 160, 392)

    ptext(c, "PHẦN CỨNG PILOT", 38, 304, 235, style(9, 11, GREEN, True))
    rounded(c, 38, 115, 235, 173, fill=WHITE)
    bullets(c, [
        "2 điện thoại cố định, một máy có LiDAR nếu sẵn có",
        "mâm xoay, mốc góc, nền xám matte",
        "đèn LED + tản sáng; khóa nét/sáng/WB",
        "cân, thước, bảng Charuco",
        "tem buộc ngoài vùng quét; không viết lên vỏ",
    ], 52, 268, 207, style(8.6, 11, INK), 5)

    ptext(c, "NHÓM TỐI THIỂU", 303, 304, 235, style(9, 11, GREEN, True))
    rounded(c, 303, 115, 235, 173, fill=WHITE)
    bullets(c, [
        "01 chủ nhiệm sản phẩm / vận hành mẫu",
        "01 kỹ sư computer vision / ML",
        "01 data engineer bán thời gian",
        "01 người lấy mẫu + 01 người kiểm tra nhãn",
        "chuyên gia grade tham gia gắn nhãn mù",
    ], 317, 268, 207, style(8.6, 11, INK), 5)

    ptext(c, "CHƯA CẦN MUA / XÂY", 568, 304, 236, style(9, 11, RED, True))
    rounded(c, 568, 115, 236, 173, fill=colors.HexColor("#FFF2EA"), stroke=colors.HexColor("#E9B6A7"))
    bullets(c, [
        "motor độ chính xác cao hoặc 4 camera",
        "database/app riêng trước khi schema ổn",
        "mesh 3D sắc từng gai làm nguồn chính",
        "deep model lớn cho pilot 60 quả",
        "tự động hóa quyết định khi chưa có abstention",
    ], 582, 268, 208, style(8.6, 11, INK), 5, RED)
    c.showPage()


def decisions(c):
    section_header(c, 15, "14 / Quyết định", "Rủi ro, kiểm soát và 30 ngày hiện tại",
                   "Khi chưa có quả nguyên vẹn mới, tháng đầu tập trung audit dữ liệu đang có và khóa SOP cho đợt lấy mẫu sau.")
    data = [
        ["Rủi ro", "Kiểm soát bắt buộc"],
        ["Model đọc chữ viết, QR hoặc nền", "Không viết lên vỏ; đổi nền/thiết bị/người chụp; audit keypoint"],
        ["Cùng video xuất hiện ở train và test", "Split ở fruit_id/session trước mọi thao tác lấy frame"],
        ["Depth/mesh tạo cảm giác chính xác giả", "LiDAR chỉ là kênh phụ; báo coverage và confidence"],
        ["Nhãn múi/cân sai", "Ảnh đối chứng, hai người kiểm tra, mass-balance và cờ REVIEW"],
        ["Mô hình quá tự tin", "Kết quả ba trạng thái; threshold khóa trước blind test"],
    ]
    simple_table(c, data, 38, 480, [245, 521], font_size=8.4, row_padding=5.5)

    ptext(c, "KẾ HOẠCH 30 NGÀY", 38, 227, 470, style(9, 11, GREEN, True))
    weeks = [
        ("TUẦN 1", "Audit video, ảnh sau bổ, cân và liên kết fruit_id của dữ liệu hiện có."),
        ("TUẦN 2", "Chạy fingerprint smoke test trước/sau khi mask chữ viết; review false match."),
        ("TUẦN 3", "Chuẩn hóa ground truth còn dùng được; chạy baseline quality nếu nhãn đủ."),
        ("TUẦN 4", "Ra báo cáo thăm dò; khóa SOP, metric và checklist cho đợt lấy mẫu mới."),
    ]
    y = 197
    for label, detail in weeks:
        chip(c, label, 38, y - 15, 74, GREEN, WHITE)
        ptext(c, escape(detail), 126, y, 382, style(8.7, 11.5, INK))
        y -= 36

    rounded(c, 540, 76, 264, 151, fill=DEEP, stroke=DEEP)
    ptext(c, "ĐỀ NGHỊ PHÊ DUYỆT TIẾP", 557, 207, 230, style(8.5, 10, colors.HexColor("#9ADBD7"), True, TA_CENTER))
    ptext(c, "Đợt sau: pilot 60 quả", 557, 180, 230, style(18, 22, WHITE, True, TA_CENTER))
    ptext(c, "30 quả có query fingerprint độc lập<br/>60 quả có ground truth sau khi bổ", 557, 148, 230, style(9.5, 13, WHITE, False, TA_CENTER))
    ptext(c, "Đầu ra: bộ dữ liệu có audit + báo cáo blind test + quyết định GO/LẶP/DỪNG cho từng dự án.", 557, 104, 230, style(8.4, 11, colors.HexColor("#DDEDE4"), True, TA_CENTER))
    c.showPage()


def tree_measurement(c):
    section_header(c, 16, "15 / Đo tại hiện trường", "Chiều cao cây và độ rộng tán",
                   "App đã có chức năng đo, nhưng số hiện trường chưa đúng; bước tiếp theo là hiệu chuẩn bằng số đo đối chứng, không sửa theo cảm giác.")

    rounded(c, 38, 220, 260, 267, fill=WHITE)
    ptext(c, "MINH HỌA PHÉP ĐO", 54, 468, 228, style(8.5, 10, GREEN, True, TA_CENTER))
    c.setStrokeColor(MUTED)
    c.setLineWidth(1.2)
    c.line(58, 254, 278, 254)
    c.setFillColor(colors.HexColor("#77563B"))
    c.rect(162, 254, 15, 90, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#A8C8B8"))
    for x, y, radius in ((170, 383, 49), (126, 369, 39), (216, 368, 40), (166, 426, 35)):
        c.circle(x, y, radius, fill=1, stroke=0)
    c.setStrokeColor(CYAN)
    c.setLineWidth(2)
    c.line(273, 254, 273, 452)
    arrow(c, 273, 420, 273, 452, CYAN, 2)
    ptext(c, "H", 278, 363, 18, style(10, 12, CYAN, True, TA_CENTER))
    c.setStrokeColor(GOLD)
    c.line(84, 374, 253, 374)
    c.line(84, 367, 84, 381)
    c.line(253, 367, 253, 381)
    ptext(c, "D1", 156, 397, 28, style(9, 11, colors.HexColor("#956B19"), True, TA_CENTER))
    c.setFillColor(DEEP)
    c.roundRect(54, 268, 23, 39, 4, fill=1, stroke=0)
    c.setStrokeColor(CYAN)
    c.line(77, 292, 164, 254)
    ptext(c, "D + góc ngọn/gốc", 56, 243, 220, style(7.8, 9.5, MUTED, True, TA_CENTER))

    rounded(c, 320, 363, 484, 124, fill=colors.HexColor("#FFF2EA"), stroke=colors.HexColor("#E9B6A7"))
    ptext(c, "TRẠNG THÁI CODE / APP", 336, 468, 452, style(8.5, 10, RED, True))
    bullets(c, [
        "App đã có màn đo và lưu chiều cao/tán cùng hồ sơ mẫu.",
        "Code lấy depth ở gốc; ngọn suy từ tia nhìn, mép tán chiếu vào một mặt phẳng đứng cố định.",
        "Nhóm hiện trường báo số chưa đúng: gắn nhãn ESTIMATE_UNVERIFIED, không dùng làm ground truth.",
    ], 334, 444, 458, style(8.5, 10.6, INK), 2, RED)

    rounded(c, 320, 220, 484, 128, fill=WHITE)
    ptext(c, "QUY TRÌNH ĐỐI CHỨNG Ở ĐỢT SAU", 336, 329, 452, style(8.5, 10, GREEN, True))
    bullets(c, [
        "App: đo 3 lần từ cùng vị trí và lưu từng lần.",
        "Chiều cao: laser/máy đo cao; hoặc H = D × (tan αtop − tan αbase).",
        "Tán: D1 rộng nhất + D2 vuông góc; độ rộng trung bình = (D1 + D2) / 2.",
        "So app theo đúng hướng D1; lưu GPS, hướng chụp, ảnh và cờ che khuất/nền dốc.",
    ], 334, 306, 458, style(8.4, 10.2, INK), 1.5)

    rounded(c, 38, 63, 766, 132, fill=DEEP, stroke=DEEP)
    ptext(c, "PILOT KIỂM ĐỊNH TỐI THIỂU", 54, 177, 734, style(8.5, 10, colors.HexColor("#9ADBD7"), True))
    checks = [
        (54, "20 cây", "trải đều thấp/cao, tán hẹp/rộng"),
        (238, "Đo lặp", "app ×3; đối chứng ×2 khi khó thấy"),
        (422, "Báo sai số", "bias, MAE, MAPE và độ lặp lại"),
        (606, "Chốt sử dụng", "đạt ngưỡng theo nghiệp vụ mới bỏ cờ"),
    ]
    for x, title, detail in checks:
        node(c, x, 82, 164, 66, title, detail, WHITE, CYAN)
    c.showPage()


def sources(c):
    section_header(c, 17, "Phụ lục", "Nguồn nội bộ và cách đọc báo cáo",
                   "Các kết quả kỹ thuật trích từ artefact có sẵn trong codebase; hình cắt lớp là minh họa khái niệm.")
    ptext(c, "TÀI LIỆU NỀN", 38, 466, 360, style(9, 11, GREEN, True))
    bullets(c, [
        "docs/durian-mvp-blueprint.md - mục tiêu, quy trình và schema ban đầu",
        "docs/durian-sample-processing-procedure.md - SOP lấy mẫu và ground truth",
        "docs/quy-trinh-rgb-body-unwrap-hien-tai.md - pipeline RGB unwrap hiện tại",
        "Code app scanner - TreeMeasurementViewController và TreeMeasurementGeometry",
        "FAO Small-Scale Postharvest Handling - đo chất rắn hòa tan bằng khúc xạ kế",
        "Applied Sciences 11(12):5653 - phương pháp Brix/chất khô trên sầu riêng",
    ], 42, 440, 360, style(7.8, 9.8, INK), 3)

    ptext(c, "ARTEFACT ĐỊNH LƯỢNG", 430, 466, 374, style(9, 11, GREEN, True))
    bullets(c, [
        "test_video/processed/video-body-unwrap/report.json",
        "test_video/processed/multiview-retrieval-prototype/report.json",
        "test_video/processed/rgbd-spike-fusion/report.json",
        "prototypes/durian_2d_projection/output-3d/pilot-manifest.csv",
    ], 434, 440, 366, style(8.4, 11, INK), 5)

    rounded(c, 38, 189, 766, 118, fill=WHITE)
    ptext(c, "PHÂN BIỆT BA LOẠI TUYÊN BỐ", 54, 287, 734, style(9, 11, INK, True))
    data = [
        ["Nhãn", "Ý nghĩa trong tài liệu"],
        ["Kết quả hiện tại", "Con số đã được ghi trong report/manifest của repo"],
        ["Đề xuất pilot", "Quy mô, metric và ngưỡng dùng để thiết kế thí nghiệm tiếp theo"],
        ["Mục tiêu sản phẩm", "Chỉ được xác nhận sau khi blind test và vận hành thực tế đạt yêu cầu"],
    ]
    simple_table(c, data, 54, 265, [130, 602], font_size=8.3, row_padding=5)

    rounded(c, 38, 74, 766, 86, fill=DEEP, stroke=DEEP)
    ptext(c, "Ghi chú hình ảnh", 54, 140, 135, style(8.5, 10, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Ảnh quét, RGB unwrap và retrieval là dữ liệu thật trong repo. Hình bìa/cắt lớp, scan cell và quét tại vườn được tạo bằng công cụ sinh ảnh để minh họa, không dùng làm dữ liệu huấn luyện hay bằng chứng mô hình.", 180, 140, 600, style(8.6, 11.5, WHITE))
    c.showPage()


def build():
    global BODY, SMALL, TINY
    register_fonts()
    BODY = style(10, 13.5, INK)
    SMALL = style(8.5, 11, MUTED)
    TINY = style(7.2, 8.8, MUTED)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(OUTPUT), pagesize=(W, H), pageCompression=1)
    document.setTitle("Chương trình AI cho sầu riêng - Fingerprint và dự báo chất lượng")
    document.setAuthor("Durian Fingerprint Lab")
    for page in (
        cover,
        executive_summary,
        shared_program,
        operating_modes,
        industrial_cell,
        field_phone,
        fingerprint_project,
        fingerprint_evidence,
        fingerprint_experiment,
        quality_project,
        quality_experiment,
        data_governance,
        roadmap,
        minimal_architecture,
        decisions,
        tree_measurement,
        sources,
    ):
        page(document)
    document.save()
    print(OUTPUT)


if __name__ == "__main__":
    build()
