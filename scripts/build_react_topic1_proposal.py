#!/usr/bin/env python3
"""Build the RE:ACT Track 1 proposal for DurianFingerprint."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/durian-id-thuyet-minh-react-chu-de-1.pdf"
ASSETS = ROOT / "output/pdf/assets"
PROTOTYPE = ASSETS / "prototype-20260922"
W, H = landscape(A4)

INK = colors.HexColor("#17332D")
DEEP = colors.HexColor("#0B2A23")
GREEN = colors.HexColor("#1F6F50")
CYAN = colors.HexColor("#27AAA5")
GOLD = colors.HexColor("#D9A441")
RED = colors.HexColor("#C95A4A")
MINT = colors.HexColor("#DDEDE4")
PALE = colors.HexColor("#F4F1E8")
WHITE = colors.white
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


def ptext(c, text, x, top, width, text_style=None):
    paragraph = Paragraph(text, text_style or style())
    _, height = paragraph.wrap(width, H)
    paragraph.drawOn(c, x, top - height)
    return top - height


def bullets(c, items, x, top, width, text_style=None, gap=5, bullet_color=GREEN):
    y = top
    for item in items:
        c.setFillColor(bullet_color)
        c.circle(x + 3, y - 6, 2.2, fill=1, stroke=0)
        y = ptext(c, item, x + 12, y, width - 12, text_style or style()) - gap
    return y


def rounded(c, x, y, width, height, fill=WHITE, stroke=LINE, radius=10):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


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


def image_contain(c, path, x, y, width, height):
    image = ImageReader(str(path))
    iw, ih = image.getSize()
    scale = min(width / iw, height / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(image, x + (width - dw) / 2, y + (height - dh) / 2, dw, dh, mask="auto")


def chip(c, text, x, y, width, fill=MINT, color=GREEN):
    c.setFillColor(fill)
    c.roundRect(x, y, width, 22, 11, fill=1, stroke=0)
    ptext(c, escape(text), x + 6, y + 16, width - 12, style(8, 10, color, True, TA_CENTER))


def footer(c, page_no):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(38, 25, W - 38, 25)
    ptext(c, "DURIANFINGERPRINT  |  RE:ACT - CHỦ ĐỀ 1  |  22.09.2026", 38, 20, 430, style(7.2, 8.5, MUTED, True))
    ptext(c, f"{page_no:02d} / 10", W - 88, 20, 50, style(7.2, 8.5, MUTED, True, TA_CENTER))


def header(c, page_no, kicker, title, subtitle=""):
    c.setFillColor(PALE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    ptext(c, escape(kicker.upper()), 38, H - 27, W - 76, style(8.3, 10, GREEN, True))
    title_bottom = ptext(c, escape(title), 38, H - 48, W - 76, style(24, 29, INK, True))
    if subtitle:
        subtitle_bottom = ptext(c, escape(subtitle), 38, min(H - 82, title_bottom - 8), W - 76, style(10.2, 14, MUTED))
        if subtitle_bottom < 486:
            raise ValueError(f"Header chạm nội dung trang {page_no}: {title}")
    footer(c, page_no)


def arrow(c, x1, y1, x2, y2, color=GREEN):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.8)
    c.line(x1, y1, x2, y2)
    c.line(x2, y2, x2 - 8, y2 + 4)
    c.line(x2, y2, x2 - 8, y2 - 4)


def node(c, x, y, width, height, title, detail, fill=WHITE, accent=GREEN):
    rounded(c, x, y, width, height, fill, LINE, 8)
    c.setFillColor(accent)
    c.roundRect(x, y, 5, height, 3, fill=1, stroke=0)
    compact = width < 160
    top = ptext(c, escape(title), x + 14, y + height - 12, width - 24, style(9.4 if compact else 10.5, 12.5, INK, True))
    ptext(c, escape(detail).replace("\n", "<br/>"), x + 14, top - 5, width - 24, style(8.6 if compact else 9.3, 11.5, MUTED))


def table(c, data, x, top, widths, font_size=9.6):
    rows = []
    for ri, row in enumerate(data):
        rows.append([
            Paragraph(escape(str(cell)), style(font_size, font_size * 1.25, WHITE if ri == 0 else INK, ri == 0))
            for cell in row
        ])
    item = Table(rows, colWidths=widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DEEP),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    for ri in range(1, len(rows)):
        commands.append(("BACKGROUND", (0, ri), (-1, ri), WHITE if ri % 2 else colors.HexColor("#EEF3EF")))
    item.setStyle(TableStyle(commands))
    _, height = item.wrap(sum(widths), H)
    item.drawOn(c, x, top - height)
    return top - height


def cover(c):
    c.setFillColor(DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    image_cover(c, ASSETS / "durian-two-projects-hero.png", 0, 175, W, H - 175)
    c.saveState()
    c.setFillColor(DEEP)
    c.setFillAlpha(0.92)
    c.rect(0, 0, W, 232, fill=1, stroke=0)
    c.restoreState()
    ptext(c, "HỒ SƠ ĐỀ XUẤT RE:ACT 2026", 38, 210, 420, style(9, 11, colors.HexColor("#9ADBD7"), True))
    ptext(c, "DURIANFINGERPRINT", 38, 181, 660, style(30, 34, WHITE, True))
    ptext(c, "Dấu vân số cho chuỗi giá trị sầu riêng minh bạch", 38, 137, 660, style(16, 20, colors.HexColor("#DDEDE4"), True))
    ptext(c, "Quét không phá hủy bằng điện thoại để tạo hồ sơ từng quả, xác minh đúng quả và xây dựng dữ liệu khách quan cho đánh giá chất lượng.", 38, 104, 700, style(10.5, 14, colors.HexColor("#B7CCC4")))
    chip(c, "CHỦ ĐỀ 1", 38, 38, 92, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    chip(c, "SINH KẾ SỐ BAO TRÙM", 140, 38, 178, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    chip(c, "PROTOTYPE SẴN SÀNG PILOT", 328, 38, 200, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    ptext(c, "Nhóm DurianFingerprint  |  22.09.2026", W - 280, 54, 242, style(8.5, 10, colors.HexColor("#B7CCC4"), True, TA_CENTER))
    c.showPage()


def problem(c):
    header(c, 2, "01 / Vấn đề cộng đồng", "Khoảng trống truy xuất đến từng quả",
           "Hồ sơ theo vùng trồng và lô hàng chưa đủ để đối chiếu chính quả sầu riêng đang được giao nhận.")
    rounded(c, 38, 304, 238, 174)
    ptext(c, "NHÀ VƯỜN", 54, 458, 206, style(9, 11, GREEN, True))
    ptext(c, "Khó chứng minh đúng nguồn gốc và chất lượng khi thương lượng giá; phụ thuộc mạnh vào đánh giá của bên mua.", 54, 429, 206, style(12, 16, INK, True))
    ptext(c, "Hệ quả: bất cân xứng thông tin và nguy cơ bị giảm giá thiếu căn cứ.", 54, 345, 206, style(9, 12, MUTED))

    rounded(c, 300, 304, 238, 174, colors.HexColor("#FFF3D9"), colors.HexColor("#E6C77B"))
    ptext(c, "NGƯỜI MUA / THƯƠNG LÁI", 316, 458, 206, style(9, 11, colors.HexColor("#956B19"), True))
    ptext(c, "Khó kiểm tra quả có đúng hồ sơ ban đầu và khó lượng hóa số múi, tỷ lệ cơm hoặc lỗi bên trong trước khi bổ.", 316, 429, 206, style(12, 16, INK, True))
    ptext(c, "Hệ quả: giao dịch dựa nhiều vào kinh nghiệm và niềm tin cá nhân.", 316, 345, 206, style(9, 12, MUTED))

    rounded(c, 562, 304, 242, 174, colors.HexColor("#E4F0ED"), colors.HexColor("#A9CBC3"))
    ptext(c, "KHOẢNG TRỐNG SỐ", 578, 458, 210, style(9, 11, CYAN, True))
    ptext(c, "Chưa có cách phổ thông, chi phí thấp để tạo hồ sơ số và kiểm tra từng quả bằng thiết bị sẵn có.", 578, 429, 210, style(12, 16, INK, True))
    ptext(c, "Cơ hội: biến điện thoại thành công cụ tạo bằng chứng dùng chung.", 578, 345, 210, style(9, 12, MUTED))

    rounded(c, 38, 72, 766, 198, DEEP, DEEP)
    ptext(c, "ĐỐI TƯỢNG HƯỞNG LỢI TRỰC TIẾP", 54, 246, 734, style(9, 11, colors.HexColor("#9ADBD7"), True))
    bullets(c, [
        "Nhà vườn và hợp tác xã cần hồ sơ nguồn gốc dễ tạo, dễ mang theo và có thể kiểm chứng.",
        "Hộ kinh doanh, điểm thu mua và đóng gói cần giảm nhầm lẫn, tráo quả và tranh chấp chất lượng.",
        "Người mua cuối cần thông tin rõ ràng hơn thay vì chỉ dựa vào tem hoặc lời cam kết.",
    ], 54, 218, 718, style(10, 13.5, WHITE), 7, CYAN)
    c.showPage()


def solution(c):
    header(c, 3, "02 / Giải pháp", "Một quả - một dấu vân số có thể kiểm chứng",
           "QR hỗ trợ quản lý; bằng chứng chính đến từ đặc trưng tự nhiên của gai, khe, dáng và vân vỏ.")
    image_cover(c, PROTOTYPE / "field-capture.jpg", 38, 126, 386, 350, 0.45)
    ptext(c, "Khung hình thử nghiệm chụp quả tại vườn", 50, 116, 362, style(7.5, 9, MUTED, False, TA_CENTER))

    node(c, 460, 392, 328, 84, "1. ĐĂNG KÝ", "Quay nhiều góc bằng điện thoại; tạo fruit_id và hồ sơ bề mặt.", colors.HexColor("#E3F0E7"))
    node(c, 460, 288, 328, 84, "2. XÁC MINH", "Quét một vùng vỏ; tìm ứng viên và kiểm tra hình học.", colors.HexColor("#E4F0ED"), CYAN)
    node(c, 460, 184, 328, 84, "3. PHẢN HỒI", "Hướng tới kết quả: khớp / chưa đủ bằng chứng / không khớp.", colors.HexColor("#FFF3D9"), GOLD)
    node(c, 460, 80, 328, 84, "4. HỌC TỪ DỮ LIỆU THẬT", "Bổ một phần mẫu, cân và ghi nhãn để xây nền cho đánh giá chất lượng.", WHITE)
    arrow(c, 624, 388, 624, 374)
    arrow(c, 624, 284, 624, 270)
    arrow(c, 624, 180, 624, 166)
    c.showPage()


def evidence(c):
    header(c, 4, "03 / Mức độ sẵn sàng", "Nền tảng kỹ thuật và dữ liệu phục vụ kiểm chứng",
           "Bộ quét, ảnh bề mặt và kết quả xử lý ban đầu tạo cơ sở cho Living Lab có đối chứng.")
    rounded(c, 38, 300, 350, 180)
    image_contain(c, PROTOTYPE / "body-texture-map.png", 48, 326, 330, 134)
    ptext(c, "Bản đồ bề mặt vỏ ghép từ nhiều góc chụp", 50, 316, 326, style(8, 10, INK, True, TA_CENTER))

    rounded(c, 410, 300, 394, 180)
    image_cover(c, PROTOTYPE / "surface-feature-overlay.jpg", 422, 326, 370, 134)
    ptext(c, "Đặc trưng vỏ được đánh dấu trên ảnh thử nghiệm", 424, 316, 366, style(8, 10, INK, True, TA_CENTER))

    rounded(c, 38, 75, 360, 190, colors.HexColor("#E3F0E7"), colors.HexColor("#A8C8B8"))
    ptext(c, "ĐÃ LÀM ĐƯỢC", 54, 244, 328, style(9, 11, GREEN, True))
    bullets(c, [
        "Bộ quét thử nghiệm, quy trình gắn sample_id và xuất dữ liệu.",
        "Tách quả, chọn view và dàn ảnh RGB 360 độ phần thân.",
        "Kết quả gần nhất: 43/48 frame, coverage 100%, bản đồ 1259 x 353 px.",
        "Prototype tìm vùng tương ứng giữa ảnh query và kho view.",
    ], 52, 218, 330, style(8.7, 11.4, INK), 5)

    rounded(c, 420, 75, 384, 190, colors.HexColor("#E4F0ED"), colors.HexColor("#A9CBC3"))
    ptext(c, "KẾ HOẠCH KIỂM CHỨNG", 436, 244, 352, style(9, 11, CYAN, True))
    bullets(c, [
        "Chuẩn hóa bộ dữ liệu nhiều quả, nhiều buổi chụp và điều kiện hiện trường.",
        "Đo cặp cùng quả / khác quả; khóa ngưỡng trước khi đánh giá.",
        "Thu ground truth sau bổ làm nền cho hướng đánh giá chất lượng.",
        "Living Lab thực hiện blind test và báo cáo kết quả theo nhóm.",
    ], 434, 218, 354, style(8.7, 11.4, INK), 5, CYAN)
    c.showPage()


def technology(c):
    header(c, 5, "04 / Công nghệ và đổi mới", "Tận dụng điện thoại và đặc trưng tự nhiên của chính quả",
           "Thiết kế chi phí thấp cho bối cảnh nhà vườn và hộ kinh doanh, không phụ thuộc tem làm bằng chứng duy nhất.")
    nodes = [
        (38, "THU NHẬN", "Video RGB nhiều góc\n+ depth phụ trợ"),
        (196, "CHUẨN HÓA", "Mask quả, QC,\n chọn view"),
        (354, "DẤU VÂN", "Gai, khe, vân vỏ,\n dáng thô"),
        (512, "SO KHỚP", "Retrieval và kiểm tra\n hình học"),
        (670, "KẾT QUẢ", "Đúng / chưa chắc / sai\n + độ tin cậy"),
    ]
    for i, (x, title, detail) in enumerate(nodes):
        node(c, x, 344, 134, 105, title, detail, WHITE, [GREEN, CYAN, GOLD, GREEN, CYAN][i])
        if i < len(nodes) - 1:
            arrow(c, x + 134, 396, x + 154, 396)

    rounded(c, 38, 82, 488, 220, DEEP, DEEP)
    ptext(c, "ĐIỂM KHÁC BIỆT", 54, 279, 456, style(9, 11, colors.HexColor("#9ADBD7"), True))
    bullets(c, [
        "Định danh ở cấp từng quả thay vì chỉ cấp lô; vẫn hoạt động khi QR bị thay hoặc mất.",
        "Người mua chỉ cần quét một vùng nhỏ, không phải dựng mô hình 3D hoàn chỉnh.",
        "Một quy trình lấy mẫu tạo đồng thời hồ sơ truy xuất và dữ liệu ground truth sau khi bổ.",
        "Kết quả ba trạng thái giúp hệ thống được phép nói 'chưa chắc' thay vì ép một dự đoán sai.",
    ], 54, 251, 456, style(9.2, 12.5, WHITE), 6, CYAN)
    image_cover(c, PROTOTYPE / "scan-rig.jpg", 540, 82, 264, 220, 0.56)
    c.saveState()
    c.setFillColor(DEEP)
    c.setFillAlpha(0.86)
    c.rect(540, 82, 264, 29, fill=1, stroke=0)
    c.restoreState()
    ptext(c, "Bộ gá quét prototype của nhóm", 548, 102, 248, style(8, 10, WHITE, True, TA_CENTER))
    c.showPage()


def living_lab(c):
    header(c, 6, "05 / Living Lab", "Pilot sáu tháng cùng nhà vườn và điểm thu mua",
           "Môi trường đề xuất: một hợp tác xã hoặc cụm nhà vườn, một điểm thu mua/đóng gói và nhóm người dùng kiểm tra độc lập.")
    data = [
        ["Giai đoạn", "Hoạt động", "Đầu ra kiểm chứng"],
        ["Tháng 1", "Khóa SOP, biểu mẫu đồng ý, mã mẫu; chọn đối tác và người dùng", "Protocol, baseline và kế hoạch dữ liệu"],
        ["Tháng 2", "Đăng ký 30 quả sạch; 2 camera, 2 vòng quay; QC ngay tại chỗ", "Kho fingerprint không có marker trên vỏ"],
        ["Tháng 3", "6 query/quả, 2 người chụp, 3 điều kiện; so với 29 quả còn lại", "Genuine/impostor và lỗi theo điều kiện"],
        ["Tháng 4", "Thu 60 quả có cân, ảnh sau bổ và nhãn từng hộc", "Dataset chất lượng có ground truth"],
        ["Tháng 5", "Khóa thuật toán trên 20 quả; blind test 10 quả mới", "Báo cáo accuracy, FAR/TAR và ca lỗi"],
        ["Tháng 6", "Thử quy trình với người dùng; phỏng vấn và đo thời gian thao tác", "Bản prototype cải tiến và báo cáo tác động"],
    ]
    table(c, data, 38, 472, [95, 382, 289], 9.5)
    rounded(c, 38, 62, 766, 70, colors.HexColor("#E3F0E7"), colors.HexColor("#A8C8B8"))
    ptext(c, "CỔNG QUYẾT ĐỊNH", 54, 112, 125, style(8.5, 10, GREEN, True))
    ptext(c, "Điều kiện mở rộng: blind test vượt baseline và hiệu năng ổn định giữa người dùng, thiết bị, điều kiện ánh sáng.", 178, 112, 610, style(9.2, 12.5, INK, True))
    c.showPage()


def impact(c):
    header(c, 7, "06 / Tác động và đo lường", "Đo cả hiệu năng kỹ thuật lẫn giá trị đối với sinh kế",
           "Các chỉ số dưới đây là mục tiêu đề xuất cho giai đoạn pilot.")
    cards = [
        (38, 328, 238, 150, "30 QUẢ", "Kho fingerprint sạch", "Mỗi quả có enrollment và query độc lập", GREEN),
        (300, 328, 238, 150, "60 QUẢ", "Ground truth chất lượng", "Cân vỏ/cơm/hạt và nhãn từng hộc", GOLD),
        (562, 328, 242, 150, "20 NGƯỜI", "Nhóm dùng thử", "Nhà vườn, người mua và vận hành", CYAN),
    ]
    for x, y, w, h, big, title, detail, accent in cards:
        rounded(c, x, y, w, h)
        ptext(c, big, x + 16, y + h - 20, w - 32, style(23, 26, accent, True))
        ptext(c, title, x + 16, y + h - 56, w - 32, style(10, 13, INK, True))
        ptext(c, detail, x + 16, y + h - 84, w - 32, style(8.5, 11, MUTED))

    data = [
        ["Nhóm chỉ số", "Chỉ số", "Mục tiêu quản trị pilot"],
        ["Kỹ thuật", "Top-1 identification; TAR tại FAR <= 1%; tỷ lệ 'chưa chắc'", "Top-1 >= 90%; TAR >= 85%; báo cáo CI theo fruit_id"],
        ["Khả dụng", "Tỷ lệ hoàn thành, thời gian quét, lỗi thao tác", ">= 80% người dùng hoàn thành không cần hỗ trợ trực tiếp"],
        ["Sinh kế", "Mức rõ ràng của căn cứ giao dịch; tranh chấp/nhầm quả được ghi nhận", ">= 70% người dùng đánh giá hồ sơ số hữu ích"],
        ["Bao trùm", "Kết quả theo vai trò, thiết bị và mức kỹ năng số", "Báo cáo chênh lệch giữa các nhóm minh bạch"],
    ]
    table(c, data, 38, 286, [110, 328, 328], 9.4)
    c.showPage()


def budget(c):
    header(c, 8, "07 / Kế hoạch nguồn lực", "Ngân sách đề xuất tối đa 15.000 USD",
           "Nguồn lực tập trung vào hiện trường, dữ liệu và đánh giá hiệu quả theo từng mốc pilot.")
    data = [
        ["Hạng mục", "USD", "Mục đích"],
        ["Tổ chức hiện trường và hỗ trợ người tham gia", "3.500", "Đi lại, thu mẫu, không gian thử nghiệm, bồi hoàn thời gian hợp lệ"],
        ["Thiết bị quét và đo kiểm", "2.500", "Rig, chiếu sáng, cân, hiệu chuẩn, lưu trữ tại chỗ"],
        ["Thu thập và gán nhãn dữ liệu", "3.000", "30 quả fingerprint; 60 quả có ground truth sau bổ"],
        ["Phát triển prototype và baseline", "3.000", "Pipeline, giao diện kiểm tra tối thiểu, logging và đánh giá"],
        ["Đánh giá, quyền riêng tư và an toàn dữ liệu", "1.500", "Biểu mẫu đồng ý, ẩn danh hóa, kiểm tra truy cập và blind test"],
        ["Workshop người dùng, tài liệu và Demo Day", "1.500", "Phản hồi, đào tạo vận hành, báo cáo và trình diễn"],
        ["TỔNG", "15.000", "Điều chỉnh theo phê duyệt và quy định chi tiêu của chương trình"],
    ]
    table(c, data, 38, 480, [250, 85, 431], 9.5)
    rounded(c, 38, 66, 766, 78, DEEP, DEEP)
    ptext(c, "NGUYÊN TẮC", 54, 124, 110, style(8.5, 10, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Mỗi khoản chi gắn với một đầu ra: dữ liệu chuẩn, thử nghiệm thực địa, đánh giá độc lập và prototype được cải tiến.", 164, 124, 624, style(9.5, 13, WHITE, True))
    c.showPage()


def governance(c):
    header(c, 9, "08 / Đội ngũ và quản trị rủi ro", "Nhóm nhỏ, vai trò rõ, dữ liệu có trách nhiệm",
           "Cơ cấu triển khai kết hợp kỹ thuật, vận hành thực địa, dữ liệu và chuyên môn ngành hàng.")
    rounded(c, 38, 292, 360, 186)
    ptext(c, "CẤU TRÚC ĐỘI HÌNH", 54, 456, 328, style(9, 11, GREEN, True))
    bullets(c, [
        "Chủ nhiệm sản phẩm / kỹ thuật thị giác máy tính.",
        "Phụ trách hiện trường và quan hệ nhà vườn.",
        "Phụ trách dữ liệu, ground truth và đánh giá.",
        "Đối tác chuyên môn sầu riêng / điểm thu mua.",
    ], 52, 430, 330, style(9, 12, INK), 7)

    rounded(c, 420, 292, 384, 186, colors.HexColor("#E4F0ED"), colors.HexColor("#A9CBC3"))
    ptext(c, "PRIVACY-BY-DESIGN", 436, 456, 352, style(9, 11, CYAN, True))
    bullets(c, [
        "Xin đồng ý cụ thể trước khi thu hình, giọng nói hoặc GPS.",
        "Tách farmer_id khỏi tên và thông tin liên hệ.",
        "Giới hạn quyền truy cập; mã hóa khi lưu và truyền.",
        "Công bố dữ liệu tổng hợp; cho phép yêu cầu sửa/xóa.",
    ], 434, 430, 354, style(9, 12, INK), 7, CYAN)

    data = [
        ["Yếu tố cần kiểm soát", "Quy trình kiểm soát"],
        ["Độc lập với marker và phông nền", "Chụp không viết trên vỏ; query khác buổi, người và khoảng cách"],
        ["Độ tin cậy dự đoán", "Ba trạng thái; khóa threshold trước blind test"],
        ["Tính đại diện dữ liệu", "Ít nhất 3 nguồn/lô; báo cáo kết quả theo nhóm"],
        ["Khả dụng tại hiện trường", "Hướng dẫn trực quan; đo tỷ lệ hoàn thành và cải tiến theo phản hồi"],
    ]
    table(c, data, 38, 256, [250, 516], 9.5)
    c.showPage()


def close(c):
    c.setFillColor(DEEP)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    image_cover(c, ASSETS / "durian-fingerprint-concept.png", 515, 0, 327, H, 0.5)
    c.saveState()
    c.setFillColor(DEEP)
    c.setFillAlpha(0.30)
    c.rect(515, 0, 327, H, fill=1, stroke=0)
    c.restoreState()
    ptext(c, "09 / ĐỀ XUẤT HỢP TÁC", 38, H - 38, 420, style(9, 11, colors.HexColor("#9ADBD7"), True))
    ptext(c, "Từ prototype kỹ thuật\nđến bằng chứng thực địa", 38, H - 78, 450, style(29, 35, WHITE, True))
    ptext(c, "DurianFingerprint xin tham gia RE:ACT để kiểm chứng một câu hỏi cụ thể:", 38, 385, 430, style(11, 15, colors.HexColor("#B7CCC4"), True))
    ptext(c, "Điện thoại có thể tạo một bằng chứng đủ tin cậy để xác minh từng quả và làm nền cho giao dịch sầu riêng minh bạch hơn hay không?", 38, 340, 430, style(16, 22, WHITE, True))
    bullets(c, [
        "Cần Living Lab cùng nhà vườn và điểm thu mua.",
        "Cần cố vấn về sản phẩm, mô hình tác động và kiểm chứng kỹ thuật.",
        "Cần nguồn lực cho dữ liệu sạch và blind test độc lập.",
    ], 42, 223, 420, style(10, 14, colors.HexColor("#DDEDE4")), 8, CYAN)
    chip(c, "DURIANFINGERPRINT", 38, 70, 150, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    chip(c, "CHỦ ĐỀ 1", 198, 70, 92, colors.HexColor("#17473B"), colors.HexColor("#BCE5D2"))
    ptext(c, "Tài liệu tham chiếu: re-act.vn | re-act.vn/hoi-dap | canva.link/wh7giehm80u5n0y", 38, 48, 455, style(7.5, 9, colors.HexColor("#B7CCC4")))
    ptext(c, "Ảnh trang này là minh họa khái niệm, không phải kết quả mô hình.", 540, 26, 270, style(7, 8.5, colors.HexColor("#DDEDE4"), False, TA_CENTER))
    c.showPage()


def build():
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=(W, H))
    c.setTitle("DurianFingerprint - Thuyết minh RE:ACT Chủ đề 1")
    c.setAuthor("Nhóm DurianFingerprint")
    c.setSubject("Sinh kế số bao trùm và giải pháp hỗ trợ")
    cover(c)
    problem(c)
    solution(c)
    evidence(c)
    technology(c)
    living_lab(c)
    impact(c)
    budget(c)
    governance(c)
    close(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    build()
