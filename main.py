import base64
import os
import requests
import html
from bs4 import BeautifulSoup

# ================= CONFIG =================
WP_URL = "https://blog.mexc.fm/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
POST_ID = 311646  # ID bài Spur Protocol
TARGET_H2_TEXT = "Spur Protocol Quiz Answers Today - December 19, 2025"
CHECK_ANSWER = "D) The cost shifts elsewhere, often affecting decentralization or users."

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

    # Tìm p chứa 'Question' và 'Answer'
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

    # 2. Tìm <h2> có text khớp
    def normalize(text):
        return (
            html.unescape(text)
            .lower()
            .replace("’", "'")
            .replace("–", "-")
            .replace("—", "-")
            .replace("\xa0", " ")
            .strip()
        )
        
    h2_tag = None
    for h2 in soup.find_all("h2"):
        h2_norm = normalize(h2.get_text())
        if "spur protocol quiz answers today" in h2_norm:
            h2_tag = h2
            break
    
    if not h2_tag:
        print("❌ Không tìm thấy H2 quiz")
        print("Rendered snippet:", old_content[:4000])
        return

    # 3. Xóa Question + Answer cũ
    removed = 0
    node = h2_tag.find_next_sibling("p")
    
    while node:
        text = node.get_text(" ", strip=True).lower()
    
        if text.startswith(("question:", "correct answer:")):
            next_node = node.find_next_sibling("p")
            node.decompose()
            removed += 1
            node = next_node
            continue
        break
    
    print(f"[+] Removed {removed} quiz <p>")

    # 4. Tạo Q/A mới
    q_tag = soup.new_tag("p")
    q_tag.append(soup.new_tag("strong"))
    q_tag.strong.string = f"Question: {question}"
    
    a_tag = soup.new_tag("p")
    a_tag.append(soup.new_tag("strong"))
    a_tag.strong.string = f"Correct Answer: {answer}"

    # 5. Chèn Q/A sau H2
    h2_tag.insert_after(a_tag)
    h2_tag.insert_after(q_tag)

    new_content = str(soup)
    print("[+] New content length:", len(new_content))

    # 6. Update & publish
    payload = {"content": new_content, "status": "publish"}
    update = requests.post(url, headers=headers, json=payload, timeout=15)
    print("🚀 Update status:", update.status_code)
    print("📄 Update response:", update.text[:500])

    if update.status_code == 200:
        print("✅ Post updated & published thành công!")
    else:
        print("❌ Error khi update")


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
