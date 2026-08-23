import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_promo_image(output_png="assets/eduevidence-promo.png", output_jpg="assets/eduevidence-promo.jpg"):
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    
    # 2K Resolution Banner / Card (1920x1080)
    width, height = 1920, 1080
    
    # Base background (Deep Cyber Slate / Navy)
    base = Image.new("RGBA", (width, height), (10, 15, 29, 255))
    draw = ImageDraw.Draw(base)
    
    # Glowing Ambient Orbs
    glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_overlay)
    
    # 1. Cyan Glow (Top-Left)
    for r in range(450, 0, -15):
        alpha = int(40 * (1 - r / 450))
        glow_draw.ellipse([220 - r, 160 - r, 220 + r, 160 + r], fill=(14, 165, 233, alpha))
        
    # 2. Indigo/Violet Glow (Bottom-Right)
    for r in range(550, 0, -15):
        alpha = int(35 * (1 - r / 550))
        glow_draw.ellipse([1650 - r, 820 - r, 1650 + r, 820 + r], fill=(99, 102, 241, alpha))

    # 3. Emerald/Sky Glow (Center Accent)
    for r in range(350, 0, -15):
        alpha = int(25 * (1 - r / 350))
        glow_draw.ellipse([980 - r, 540 - r, 980 + r, 540 + r], fill=(16, 185, 129, alpha))

    glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(35))
    base = Image.alpha_composite(base, glow_overlay)
    draw = ImageDraw.Draw(base)
    
    # Subtle Background Grid
    grid_color = (255, 255, 255, 10)
    grid_step = 80
    for x in range(0, width, grid_step):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, grid_step):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Fonts Setup
    font_path_zh = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    font_path_en_bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font_path_en_reg = "/System/Library/Fonts/Supplemental/Arial.ttf"
    
    def get_font(path, size, index=0):
        try:
            return ImageFont.truetype(path, size, index=index)
        except:
            return ImageFont.load_default()

    font_badge = get_font(font_path_zh, 21)
    font_title = get_font(font_path_en_bold, 78)
    font_subtitle_en = get_font(font_path_en_bold, 30)
    font_subtitle_zh = get_font(font_path_zh, 24)
    font_card_title = get_font(font_path_zh, 24)
    font_card_desc = get_font(font_path_zh, 19)
    font_tag = get_font(font_path_zh, 17)
    font_stat_val = get_font(font_path_en_bold, 44)
    font_stat_lbl = get_font(font_path_zh, 20)
    font_code = get_font(font_path_en_bold, 20)

    # ================= LEFT HERO SECTION =================
    left_x = 110
    
    # 1. Pill Badge
    badge_x, badge_y = left_x, 100
    badge_w, badge_h = 430, 46
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=23, fill=(30, 41, 59, 210), outline=(56, 189, 248, 140), width=1)
    draw.ellipse([badge_x + 18, badge_y + 17, badge_x + 30, badge_y + 29], fill=(56, 189, 248, 255))
    draw.text((badge_x + 40, badge_y + 11), "AI Agent Skill · 循证教育决策引擎", font=font_badge, fill=(186, 230, 253, 255))

    # 2. Main Title: EduEvidence
    title_y = 180
    draw.text((left_x, title_y), "EduEvidence", font=font_title, fill=(255, 255, 255, 255))
    
    # 3. Subtitles
    sub_y = title_y + 100
    draw.text((left_x, sub_y), "From Education Questions to Evidence-Based Decisions", font=font_subtitle_en, fill=(56, 189, 248, 255))
    draw.text((left_x, sub_y + 46), "让每一项教育与教学决策，都有顶刊真实学术证据与科学法庭支撑", font=font_subtitle_zh, fill=(203, 213, 225, 255))

    # 4. Description Paragraph
    desc_y = sub_y + 98
    desc_lines = [
        "• 拒绝 LLM 幻觉与凭空臆测，告别「能不能用/好不好用」的二元简单回答",
        "• 深度融合 PNAS / CHI / ACL / 教育实证研究与经典元分析知识库",
        "• 提供「四态决策模型 + 多智能体证据法庭 + 实验设计 + 数据分析」全闭环"
    ]
    for i, line in enumerate(desc_lines):
        draw.text((left_x, desc_y + i * 36), line, font=font_card_desc, fill=(148, 163, 184, 255))

    # 5. Three Key Value Pillars (Cards at bottom left)
    pillars = [
        ("⚖️ 四态科学决策", "ADOPT / PILOT", "REJECT / INSUFFICIENT", (34, 197, 94, 200)),
        ("🔬 多智能体法庭", "提炼 · 辩护 · 质询", "合议仲裁 4 重严谨校验", (56, 189, 248, 200)),
        ("🔄 全周期研究闭环", "文献综述 → 缺口识别", "实验设计 → 实证分析", (168, 85, 247, 200)),
    ]
    
    pillar_y = 550
    card_w = 275
    card_h = 160
    card_gap = 25
    
    for idx, (p_title, line1, line2, border_c) in enumerate(pillars):
        cx = left_x + idx * (card_w + card_gap)
        draw.rounded_rectangle([cx, pillar_y, cx + card_w, pillar_y + card_h], radius=16, fill=(15, 23, 42, 230), outline=border_c, width=1)
        draw.rounded_rectangle([cx + 16, pillar_y + 18, cx + 22, pillar_y + 44], radius=3, fill=border_c)
        draw.text((cx + 32, pillar_y + 18), p_title, font=font_card_title, fill=(248, 250, 252, 255))
        
        draw.text((cx + 18, pillar_y + 72), line1, font=font_tag, fill=(203, 213, 225, 255))
        draw.text((cx + 18, pillar_y + 104), line2, font=font_tag, fill=(148, 163, 184, 255))

    # ================= RIGHT DASHBOARD / FEATURE PREVIEW =================
    right_x = 1060
    right_y = 100
    right_w = 750
    right_h = 610
    
    # Outer Glassmorphism Card
    draw.rounded_rectangle([right_x, right_y, right_x + right_w, right_y + right_h], radius=22, fill=(17, 24, 39, 220), outline=(75, 85, 99, 120), width=1)
    
    # Header of Right Panel
    header_h = 64
    draw.rounded_rectangle([right_x, right_y, right_x + right_w, right_y + header_h], radius=22, fill=(30, 41, 59, 180))
    draw.ellipse([right_x + 24, right_y + 25, right_x + 38, right_y + 39], fill=(239, 68, 68, 220))
    draw.ellipse([right_x + 48, right_y + 25, right_x + 62, right_y + 39], fill=(245, 158, 11, 220))
    draw.ellipse([right_x + 72, right_y + 25, right_x + 86, right_y + 39], fill=(34, 197, 94, 220))
    draw.text((right_x + 110, right_y + 20), "EduEvidence Research Framework & Ecosystem", font=get_font(font_path_en_bold, 19), fill=(226, 232, 240, 255))

    # Inner Content Items
    item_y = right_y + 85
    items = [
        ("⚡ 零三方依赖原生架构 (Native Core)", "纯 Python 3 标准库打造，零额外依赖包，免配置、极速启动、离线可用", "0 Deps"),
        ("🤖 全主流 AI Agent 平台支持", "一键适配 Claude Code / Codex / OMP / OpenCode / Kimi / Grok / Copilot 等", "10+ Hosts"),
        ("📑 决策与研究双层交互报告", "面向教育管理者的速览建议 + 面向学术研究者的完整实证证据链下钻", "Dual-Layer"),
        ("🔒 冻结式科学铁律 (Frozen Science Rule)", "严格要求实证依据支撑，严禁凭空生成实验方案，全面关联 Gap ID 溯源", "Auditable")
    ]

    for idx, (title_str, sub_str, badge_str) in enumerate(items):
        iy = item_y + idx * 122
        # Mini Card
        draw.rounded_rectangle([right_x + 20, iy, right_x + right_w - 20, iy + 106], radius=14, fill=(11, 17, 32, 230), outline=(51, 65, 85, 130), width=1)
        
        draw.text((right_x + 36, iy + 18), title_str, font=font_card_title, fill=(241, 245, 249, 255))
        draw.text((right_x + 36, iy + 58), sub_str, font=font_tag, fill=(148, 163, 184, 255))
        
        # Badge right
        badge_w_val = 112
        draw.rounded_rectangle([right_x + right_w - 36 - badge_w_val, iy + 18, right_x + right_w - 36, iy + 50], radius=8, fill=(30, 58, 138, 200), outline=(56, 189, 248, 160), width=1)
        draw.text((right_x + right_w - 30 - badge_w_val + 10, iy + 23), badge_str, font=get_font(font_path_en_bold, 15), fill=(186, 230, 253, 255))

    # ================= BOTTOM BAR (INSTALL & REPO INFO) =================
    bar_y = 760
    bar_w = width - 220
    draw.rounded_rectangle([left_x, bar_y, left_x + bar_w, bar_y + 200], radius=20, fill=(15, 23, 42, 240), outline=(56, 189, 248, 100), width=1)
    
    # Left part of bottom bar: Install command box
    cmd_box_x = left_x + 32
    cmd_box_y = bar_y + 32
    cmd_box_w = 880
    cmd_box_h = 136
    draw.rounded_rectangle([cmd_box_x, cmd_box_y, cmd_box_x + cmd_box_w, cmd_box_y + cmd_box_h], radius=12, fill=(3, 7, 18, 255), outline=(30, 41, 59, 255), width=1)
    
    draw.text((cmd_box_x + 24, cmd_box_y + 20), "$ git clone https://github.com/37chengshan/eduevidence.git", font=font_code, fill=(248, 250, 252, 255))
    draw.text((cmd_box_x + 24, cmd_box_y + 56), "$ cd eduevidence && bash install.sh --skill", font=font_code, fill=(56, 189, 248, 255))
    draw.text((cmd_box_x + 24, cmd_box_y + 94), "✨ 支持自动检测当前环境（Claude Code, OMP, Codex, OpenCode 等）并一键激活", font=font_tag, fill=(100, 116, 139, 255))

    # Right part of bottom bar: Stats / Open Source Badges
    stats_x = cmd_box_x + cmd_box_w + 60
    stats = [
        ("100%", "开源可溯源"),
        ("10+", "主流宿主支持"),
        ("4-State", "循证决策框架"),
    ]
    for s_i, (num, lbl) in enumerate(stats):
        sx = stats_x + s_i * 230
        draw.text((sx, bar_y + 50), num, font=font_stat_val, fill=(56, 189, 248, 255))
        draw.text((sx, bar_y + 115), lbl, font=font_stat_lbl, fill=(203, 213, 225, 255))

    # Save Output
    rgb_img = base.convert("RGB")
    rgb_img.save(output_png, quality=95)
    rgb_img.save(output_jpg, quality=95)
    print(f"Generated promo images:\n - {output_png}\n - {output_jpg}")

if __name__ == "__main__":
    create_promo_image()
