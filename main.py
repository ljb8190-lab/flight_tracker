import os
import requests
from serpapi import GoogleSearch

# 1. 환경 변수에서 Secrets 값 가져오기
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 추적할 항공권 정보 및 목표가 설정
ORIGIN = "ICN"               # 출발지 (인천: ICN, 김포: GMP)
DESTINATION = "HKG"          # 목적지 (홍콩: HKG)
DEPART_DATE = "2026-11-26"   # 출발일 (YYYY-MM-DD)
RETURN_DATE = "2026-11-29"   # 귀국일 (YYYY-MM-DD)
TARGET_PRICE = 500000        # 알림받을 목표 가격 (원 단위)

def send_telegram_msg(message):
    """텔레그램 푸시 알림 전송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("텔레그램 알림 전송 성공")
    except Exception as e:
        print(f"텔레그램 알림 전송 실패: {e}")

def parse_flight_details(flight_item):
    """개별 항공권 아이템에서 항공사, 시간, 가격, 소요시간 정보 추출"""
    price = flight_item.get("price", 0)
    flights = flight_item.get("flights", [])
    
    if not flights:
        return None

    # 가는 편 / 오는 편 정보 분리
    outbound = flights[0] if len(flights) > 0 else {}
    return_flight = flights[1] if len(flights) > 1 else outbound

    # 항공사
    airline = outbound.get("airline", "항공사 미정")
    
    # 시간 정보 (출발 -> 도착)
    out_dep_time = outbound.get("departure_airport", {}).get("time", "").split()[-1] if outbound.get("departure_airport") else ""
    out_arr_time = outbound.get("arrival_airport", {}).get("time", "").split()[-1] if outbound.get("arrival_airport") else ""
    
    ret_dep_time = return_flight.get("departure_airport", {}).get("time", "").split()[-1] if return_flight.get("departure_airport") else ""
    ret_arr_time = return_flight.get("arrival_airport", {}).get("time", "").split()[-1] if return_flight.get("arrival_airport") else ""

    # 비행 방식 (직항/경유)
    layovers = flight_item.get("layovers", [])
    flight_type = "직항" if not layovers else f"경유 {len(layovers)}회"

    # 전체 소요시간 (분 -> 시간/분 변환)
    total_duration_min = flight_item.get("total_duration", 0)
    hours = total_duration_min // 60
    mins = total_duration_min % 60
    duration_str = f"{hours}시간 {mins}분" if hours else f"{mins}분"

    return {
        "price": price,
        "airline": airline,
        "flight_type": flight_type,
        "duration": duration_str,
        "outbound_time": f"{out_dep_time} ➔ {out_arr_time}" if out_dep_time else "시간 정보 없음",
        "return_time": f"{ret_dep_time} ➔ {ret_arr_time}" if ret_dep_time else "시간 정보 없음"
    }

def get_top_flight_offers():
    """SerpApi를 통해 Google Flights 상위 3개 최저가 항공권 조회"""
    params = {
        "engine": "google_flights",
        "departure_id": ORIGIN,
        "arrival_id": DESTINATION,
        "outbound_date": DEPART_DATE,
        "return_date": RETURN_DATE,
        "currency": "KRW",
        "hl": "ko",
        "gl": "kr",
        "api_key": SERPAPI_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    best_flights = results.get("best_flights", [])
    other_flights = results.get("other_flights", [])
    all_flights = best_flights + other_flights

    if not all_flights:
        print("조회된 항공권 결과가 없습니다.")
        return [], None

    # 가격순 정렬 후 상위 3개 추출
    sorted_flights = sorted(all_flights, key=lambda x: x.get("price", float("inf")))
    top_3 = sorted_flights[:3]

    parsed_offers = []
    for item in top_3:
        parsed = parse_flight_details(item)
        if parsed:
            parsed_offers.append(parsed)

    search_metadata = results.get("search_metadata", {})
    google_flights_url = search_metadata.get("google_flights_url", f"https://www.google.com/travel/flights?q=Flights%20to%20{DESTINATION}%20from%20{ORIGIN}")

    return parsed_offers, google_flights_url

def main():
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SERPAPI_KEY]):
        print("에러: GitHub Secrets에 필요한 토큰/키(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SERPAPI_KEY)가 설정되어 있지 않습니다.")
        return

    print(f"[{ORIGIN} ➔ {DESTINATION}] 최저가 후보 3개 조회를 시작합니다...")
    offers, booking_url = get_top_flight_offers()

    if not offers:
        print("가격을 불러오지 못했습니다.")
        return

    lowest_price = offers[0]["price"]
    print(f"조회 완료! 최저가: {lowest_price:,}원 / 목표가: {TARGET_PRICE:,}원")

    # 목표 가격 이하일 때만 텔레그램 푸시 알림 전송
    if lowest_price <= TARGET_PRICE:
        msg = f"✈️ *목표가 달성! 항공권 최저가 TOP 3*\n\n"
        msg += f"• *노선:* {ORIGIN} ➔ {DESTINATION}\n"
        msg += f"• *일정:* {DEPART_DATE} ~ {RETURN_DATE}\n"
        msg += f"• *목표가:* {TARGET_PRICE:,}원\n"
        msg += f"───────────────\n\n"

        for idx, offer in enumerate(offers, 1):
            msg += f"*[후보 {idx}] {offer['price']:,}원* ({offer['airline']} / {offer['flight_type']})\n"
            msg += f"• 가는편: {offer['outbound_time']}\n"
            msg += f"• 오는편: {offer['return_time']}\n"
            msg += f"• 소요시간: {offer['duration']}\n\n"

        msg += f"👉 [Google 항공권에서 예약하기]({booking_url})"
        send_telegram_msg(msg)
    else:
        print("현재 최저가가 목표가보다 높아 알림을 전송하지 않습니다.")

if __name__ == "__main__":
    main()
