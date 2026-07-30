[이재빈 (11.96.72.99)] 2026-07-30 09:20
import os
import requests

# 1. 환경 변수 (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")  # SerpApi 구글 항공권 API 키

# 2. 여정 설정 (예시: 인천 ⇄ 후쿠오카 / 원하는 노선으로 변경 가능)
DEPARTURE_AIRPORT = "ICN"  # 출발 공항 (인천)
ARRIVAL_AIRPORT = "HKG"    # 도착 공항 (홍콩)

OUTBOUND_DATE = "2026-11-26"  # 왕편 날짜
RETURN_DATE = "2026-11-29"    # 복편 날짜
MAX_PRICE = 450000            # 목표 감시 가격 (원)

def send_telegram_msg(message):
    """텔레그램 메시지 발송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("텔레그램 알림 전송 성공")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def check_flights():
    """Google Flights API(via SerpApi)를 통해 왕편/복편 항공권 조회"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": DEPARTURE_AIRPORT,
        "arrival_id": ARRIVAL_AIRPORT,
        "outbound_date": OUTBOUND_DATE,
        "outbound_times": "6,14",
        "return_date": RETURN_DATE,
        "return_time": "12,22",
        "currency": "KRW",
        "hl": "ko",
        "api_key": SERPAPI_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        best_flights = data.get("best_flights", [])
        matched_deals = []

        for flight in best_flights:
            price = flight.get("price", 0)
            
            # 목표 가격 이하인 항공권만 추출
            if price <= MAX_PRICE:
                legs = flight.get("flights", [])
                
                # legs[0]은 왕편, legs[1]은 복편 정보
                outbound_leg = legs[0] if len(legs) > 0 else {}
                return_leg = legs[1] if len(legs) > 1 else {}

                matched_deals.append({
                    "price": price,
                    # 왕편 정보
                    "out_airline": outbound_leg.get("airline", "항공사 미상"),
                    "out_dep_time": outbound_leg.get("departure_token", {}).get("time", "시간 미상"),
                    "out_arr_time": outbound_leg.get("arrival_token", {}).get("time", "시간 미상"),
                    # 복편 정보 (왕편과 명확히 구분)
                    "ret_airline": return_leg.get("airline", "항공사 미상"),
                    "ret_dep_time": return_leg.get("departure_token", {}).get("time", "시간 미상"),
                    "ret_arr_time": return_leg.get("arrival_token", {}).get("time", "시간 미상"),
                })

        return matched_deals

    except Exception as e:
        print(f"항공권 조회 중 오류 발생: {e}")
        return []

def main():
    print(f"[{DEPARTURE_AIRPORT} ⇄ {ARRIVAL_AIRPORT}] 항공권 특가/취소표 감시 시작...")
    deals = check_flights()

    if deals:
        msg = f"✈️ *목표 가격 이하 항공권 발견!*\n\n"
        msg += f"• *구간:* {DEPARTURE_AIRPORT} ⇄ {ARRIVAL_AIRPORT}\n"
        msg += f"• *일정:* {OUTBOUND_DATE} ~ {RETURN_DATE}\n"
        msg += f"───────────────\n\n"

        for deal in deals:
            msg += f"💰 *총 왕복 요금:* {deal['price']:,}원\n"
            msg += f"🛫 *가는 편 ({deal['out_airline']}):* {deal['out_dep_time']} 출발\n"
            msg += f"🛬 *오는 편 ({deal['ret_airline']}):* {deal['ret_dep_time']} 출발\n\n"

