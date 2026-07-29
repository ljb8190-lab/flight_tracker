import os
import requests

# 1. 환경 변수에서 텔레그램 정보 가져오기
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 2. 설정: 목표 가격 및 추적 정보
TARGET_PRICE = 400000  # 원하시는 목표 가격 (원 단위)
ORIGIN = "ICN"         # 출발지 (인천)
DESTINATION = "GUM"    # 목적지 (예: 괌 GUM, 오키나와 OKA 등)
DEPART_DATE = "2026-11-01" # 출발일
RETURN_DATE = "2026-11-05" # 귀국일

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def check_flights():
    # 예시: SerpApi 등의 구글 플라이트 API 엔드포인트 요청 또는 웹 스크래핑 로직
    # 만약 SerpApi 키가 없다면 아래는 기본 구조 예시입니다.
    # 실제로 작동하는 최저가 확인 API 호출
    search_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{DESTINATION}%20from%20{ORIGIN}%20on%20{DEPART_DATE}%20through%20{RETURN_DATE}"
    
    # (여기서 최저가를 가져왔다고 가정, 실제 수집된 가격)
    current_lowest_price = 350000  # 예시 수치

    print(f"현재 최저가: {current_lowest_price}원 / 목표가: {TARGET_PRICE}원")

    # 목표가보다 낮을 경우 텔레그램 푸시 알림 전송
    if current_lowest_price <= TARGET_PRICE:
        msg = (
            f"✈️ *항공권 가격 하락 알림!*\n\n"
            f"• 노선: {ORIGIN} ➔ {DESTINATION}\n"
            f"• 일정: {DEPART_DATE} ~ {RETURN_DATE}\n"
            f"• 현재 최저가: *{current_lowest_price:,}원*\n"
            f"• 목표가: {TARGET_PRICE:,}원\n\n"
            f"🔗 [구글 항공권 예약하러 가기]({search_url})"
        )
        send_telegram_msg(msg)

if __name__ == "__main__":
    check_flights()
