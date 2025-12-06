import base64
import os
import requests
from bs4 import BeautifulSoup

# ================= CONFIG =================
WP_URL = "https://blog.mexc.com/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
POST_ID = 304392  # ID bài Spur Protocol
TARGET_H2_TEXT = "Spur Protocol Quiz Answers Today for December 6, 2025"
CHECK_ANSWER = "D) DeFi and NFTS."

# find & replace
OLD_DATE = "December 6"
NEW_DATE = "December 7"


# ================ SCRAPE SITE ================
def scrape_quiz_site():
    url = "https://miningcombo.com/spur-protocol/"
    print(f"[+] Scraping quiz from {url}")
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    ps = soup.find_all("p", class_="has-text-align-left")
    if not ps or len(ps) < 2:
        raise RuntimeError("❌ Không tìm thấy đủ thẻ <p class='has-text-align-left'>")

    question = None
    answer = None
    for p in ps:
        text = p.get_text(strip=True)
        if "Question:" in text:
            question = text.replace("Question:", "").strip()
        elif "Answer:" in text:
            answer = text.replace("Answer:", "").strip()

    if not question or not answer:
        raise RuntimeError("❌ Không trích xuất được question hoặc answer")

    print("[+] Scraped question and answer")
    print("   Q:", question)
    print("   A:", answer)
    return question, answer


# ================ UPDATE POST ================
def update_post_after_h2(target_h2_text, question, answer):
    if not WP_USERNAME or not WP_APP_PASSWORD:
        raise RuntimeError("⚠️ Thiếu repo secret: WP_USERNAME hoặc WP_APP_PASSWORD")

    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {
        "Authorization": f"Basic {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    # 1. Fetch current post
    url = f"{WP_URL}/{POST_ID}"
    response = requests.get(url, headers=headers, timeout=15)
    print("🔎 Fetch status:", response.status_code)
    if response.status_code != 200:
        print("❌ Không lấy được post:", response.text[:300])
        return

    post = response.json()
    old_content = post.get("content", {}).get("rendered", "")
    if not old_content:
        print("❌ Không thấy content.rendered")
        return

    print("✍️ Lấy content.rendered, độ dài:", len(old_content))
    soup = BeautifulSoup(old_content, "html.parser")

    # 2. Tìm <h2> khớp text
    h2_tag = soup.find("h2", string=lambda t: t and target_h2_text in t)
    if not h2_tag:
        print("❌ Không tìm thấy H2 phù hợp")
        print("Rendered snippet:", old_content[:400])
        return

    # 3. Xoá toàn bộ <p> sau H2 (đang là Q/A cũ)
    next_tag = h2_tag.find_next_sibling()
    removed = 0
    while next_tag and next_tag.name == "p":
        nxt = next_tag.find_next_sibling()
        next_tag.decompose()
        next_tag = nxt
        removed += 1
    print(f"[+] Removed {removed} <p> cũ sau H2")

    # 4. Tạo đoạn Q/A mới
    p_tag = soup.new_tag("p")
    p_tag["style"] = "font-size:17px"

    strong_q = soup.new_tag("strong")
    strong_q.string = f"The question for {NEW_DATE}, 2025:"
    p_tag.append(strong_q)
    p_tag.append(f" {question}\n")

    strong_a_label = soup.new_tag("strong")
    strong_a_label.string = "Correct Answer:"
    p_tag.append(strong_a_label)
    p_tag.append(" ")

    strong_a = soup.new_tag("strong")
    strong_a.string = answer
    p_tag.append(strong_a)

    # 5. Chèn Q/A mới sau H2
    h2_tag.insert_after(p_tag)

    # 6. Find & replace ngày trong content
    new_content = str(soup).replace(OLD_DATE, NEW_DATE)
    print("[+] New content length:", len(new_content))

    # ---- UPDATE CONTENT ----
    payload = {"content": new_content, "status": "publish"}
    update = requests.post(url, headers=headers, json=payload, timeout=15)
    print("🚀 Update content status:", update.status_code)

    if update.status_code != 200:
        print("❌ Error khi update content")
        return

    print("✅ Content updated & published!")

    # ============================
    # UPDATE WP TITLE (NO SEO)
    # ============================

    updated_post = update.json()
    current_title = updated_post.get("title", {}).get("rendered", "")

    new_title = current_title.replace(OLD_DATE, NEW_DATE)

    title_payload = {
        "title": new_title
    }

    title_update = requests.post(url, headers=headers, json=title_payload, timeout=15)
    print("📝 Update Title status:", title_update.status_code)

    if title_update.status_code == 200:
        print("✅ WP Post Title updated!")
    else:
        print("⚠️ Title update failed (content still OK)")


# ================ MAIN =================
if __name__ == "__main__":
    try:
        q, a = scrape_quiz_site()
        if a.strip() != CHECK_ANSWER.strip():
            print("✅ Answer khác CHECK_ANSWER -> Update ngay")
            update_post_after_h2(TARGET_H2_TEXT, q, a)
        else:
            print("⚠️ Answer trùng CHECK_ANSWER -> Không cần update")
    except Exception as e:
        print("❌ Lỗi khi scrape hoặc update:", e)
