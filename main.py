import os
import requests
from datetime import datetime

# 1. 환경 변수 (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 항공권 조회 조건 설정
DEPARTURE_AIRPORT = "ICN"  # 인천
ARRIVAL_AIRPORT = "HKG"    # 홍콩

OUTBOUND_DATE = "2026-11-26"  # 가는 날 (목)
RETURN_DATE = "2026-11-29"    # 오는 날 (일)

# 🕒 시간대 범위 설정 (24시간제 HH:MM)
OUT_DEP_START = "06:00"  # 가는 편 출발 시작
OUT_DEP_END   = "15:00"  # 가는 편 출발 마감

RET_DEP_START = "12:00"  # 오는 편 출발 시작
RET_DEP_END   = "22:00"  # 오는 편 출발 마감

MAX_PRICE = 550000  # 목표 감시 가격 (원) - 상황에 맞게 금액 조절 가능

# 🇰🇷 국내 항공사 정의 목록
KOREAN_AIRLINES = [
    "Korean Air", "대한항공", 
    "Asiana Airlines", "아시아나항공", 
    "Jeju Air", "제주항공", 
    "Jin Air", "진에어", 
    "T'way Air", "티웨이항공", 
    "Air Busan", "에어부산", 
    "Air Seoul", "에어서울", 
    "Aero K", "에어로케이"
]

def is_korean_airline(airline_name):
    """국내 항공사 여부 체크"""
    if not airline_name:
        return False
    return any(kr_name.lower() in str(airline_name).lower() for kr_name in KOREAN_AIRLINES)

def parse_time_to_24h(time_str):
    """'9:30 AM' 또는 '09:30' 형태의 시간을 '09:30' (24시간제) 포맷으로 정규화"""
    if not time_str:
        return ""
    time_str = str(time_str).strip()
    
    # 1) 이미 24시간제 포맷인 경우 ("09:30")
    if "AM" not in time_str and "PM" not in time_str:
        parts = time_str.split(":")
        if len(parts) >= 2:
            try:
                return f"{int(parts[0]):02d}:{int(parts[1][:2]):02d}"
            except:
                return time_str
        return time_str
    
    # 2) 12시간제 AM/PM 포맷인 경우 ("09:30 AM")
    try:
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.strftime("%H:%M")
    except:
        # 분 추출 실패 시 간단 분리 예외 처리
        try:
            time_part, ampm = time_str.split()
            hh, mm = map(int, time_part.split(":"))
            if ampm.upper() == "PM" and hh < 12:
                hh += 12
            elif ampm.upper() == "AM" and hh == 12:
                hh = 0
            return f"{hh:02d}:{mm:02d}"
        except:
            return time_str

def send_telegram_msg(message):
    """텔레그램 메시지 발송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("텔레그램 알림 전송 성공")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def check_flights():
    """Google Flights API(via SerpApi)를 통한 항공권 조회 및 안전 파싱"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": DEPARTURE_AIRPORT,
        "arrival_id": ARRIVAL_AIRPORT,
        "outbound_date": OUTBOUND_DATE,
        "return_date": RETURN_DATE,
        "currency": "KRW",
        "hl": "ko",
        "api_key": SERPAPI_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        flights_list = data.get("best_flights", []) + data.get("other_flights", [])
        print(f"🔍 API 응답 데이터 수집 완료 (총 {len(flights_list)}개 항목)")

        matched_deals = []

        for idx, flight in enumerate(flights_list, 1):
            price = flight.get("price", 0)
            legs = flight.get("flights", [])
            
            # 비행 정보 객체가 유효하지 않은 항목 예외 처리
            if not legs:
                print(f"[{idx}] 스킵: 세부 비행 정보(legs) 없음")
                continue

            # 🛠️ 안전한 왕편/복편 데이터 파싱
            if len(legs) >= 2:
                # 완벽한 왕복 2개 구간이 별도로 존재하는 경우
                outbound_leg = legs[0]
                return_leg = legs[1]
                
                out_airline = outbound_leg.get("airline", "미상")
                ret_airline = return_leg.get("airline", "미상")

                raw_out_dep = outbound_leg.get("departure_token", {}).get("time") or outbound_leg.get("departure_time", "")
                raw_out_arr = outbound_leg.get("arrival_token", {}).get("time") or outbound_leg.get("arrival_time", "")
                
                raw_ret_dep = return_leg.get("departure_token", {}).get("time") or return_leg.get("departure_time", "")
                raw_ret_arr = return_leg.get("arrival_token", {}).get("time") or return_leg.get("arrival_time", "")
                
                out_flight_no = outbound_leg.get("flight_number", "")
                ret_flight_no = return_leg.get("flight_number", "")
            else:
                # 단일 legs 구조로 압축되어 들어오는 최상단 묶음 항공권 예외 처리
                outbound_leg = legs[0]
                out_airline = outbound_leg.get("airline", "미상")
                ret_airline = out_airline
                
                raw_out_dep = outbound_leg.get("departure_token", {}).get("time") or outbound_leg.get("departure_time", "")
                raw_out_arr = outbound_leg.get("arrival_token", {}).get("time") or outbound_leg.get("arrival_time", "")
                
                # 상위 객체의 시간 및 정보 보완
                raw_ret_dep = flight.get("return_departure_time", raw_out_dep)
                raw_ret_arr = flight.get("return_arrival_time", raw_out_arr)
                
                out_flight_no = outbound_leg.get("flight_number", "")
                ret_flight_no = out_flight_no

            # 시간제 변환 (24시간제 HH:MM)
            out_dep_time = parse_time_to_24h(raw_out_dep)
            out_arr_time = parse_time_to_24h(raw_out_arr)
            ret_dep_time = parse_time_to_24h(raw_ret_dep)
            ret_arr_time = parse_time_to_24h(raw_ret_arr)

            print(f"[{idx}] {out_airline}/{ret_airline} | {price:,}원 | 가는편: {out_dep_time} | 오는편: {ret_dep_time}")

            # 1) 가격 조건 필터링
            if price > MAX_PRICE:
                print(f"  └ ❌ 가격 초과 (목표: {MAX_PRICE:,}원 / 현재: {price:,}원)")
                continue

            # 2) 시간대 조건 필터링
            if not (OUT_DEP_START <= out_dep_time <= OUT_DEP_END):
                print(f"  └ ❌ 가는 편 시간 불일치 ({out_dep_time} / 기준: {OUT_DEP_START}~{OUT_DEP_END})")
                continue

            if not (RET_DEP_START <= ret_dep_time <= RET_DEP_END):
                print(f"  └ ❌ 오는 편 시간 불일치 ({ret_dep_time} / 기준: {RET_DEP_START}~{RET_DEP_END})")
                continue

            print("  └ ✅ 모든 조건 만족! 수집 완료")

            # 🇰🇷 국내 항공사 포함 여부 (어느 한쪽이라도 국내 항공사면 우선순위 반영)
            is_out_kr = is_korean_airline(out_airline)
            is_ret_kr = is_korean_airline(ret_airline)
            has_korean = is_out_kr or is_ret_kr

            matched_deals.append({
                "price": price,
                "is_korean": has_korean,
                "out_airline": out_airline,
                "out_flight_no": out_flight_no,
                "out_dep_time": out_dep_time,
                "out_arr_time": out_arr_time,
                "ret_airline": ret_airline,
                "ret_flight_no": ret_flight_no,
                "ret_dep_time": ret_dep_time,
                "ret_arr_time": ret_arr_time,
            })

        return matched_deals

    except Exception as e:
        print(f"항공권 조회 중 오류 발생: {e}")
        return []

def main():
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SERPAPI_KEY]):
        print("에러: GitHub Secrets 설정(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SERPAPI_KEY)이 누락되었습니다.")
        return

    print(f"[{DEPARTURE_AIRPORT} ⇄ {ARRIVAL_AIRPORT} / {OUTBOUND_DATE} ~ {RETURN_DATE}] 항공권 감시 시작...")
    deals = check_flights()

    if deals:
        # 1순위: 국내 항공사 포함 여부(True가 우선), 2순위: 가격 순 정렬
        sorted_deals = sorted(deals, key=lambda x: (not x['is_korean'], x['price']))[:5]
        has_kr_airline = any(deal['is_korean'] for deal in sorted_deals)

        msg = f"✈️ *조건에 맞는 홍콩 항공권 발견!*\n\n"
        msg += f"• *구간:* 인천(ICN) ⇄ 홍콩(HKG)\n"
        msg += f"• *일정:* {OUTBOUND_DATE} ~ {RETURN_DATE}\n"
        msg += f"• *안내:* {'🇰🇷 국내 항공사 우선 표시' if has_kr_airline else '🌐 외항사 검색 결과'}\n"
        msg += f"───────────────\n\n"

        for deal in sorted_deals:
            badge = "🇰🇷 " if deal['is_korean'] else "🌐 "
            msg += f"💰 *왕복 총액:* {deal['price']:,}원\n"
            msg += f"🛫 *가는 편 ({badge}{deal['out_airline']} {deal['out_flight_no']})*\n"
            msg += f"   시간: {deal['out_dep_time']} ➔ {deal['out_arr_time']}\n"
            msg += f"🛬 *오는 편 ({badge}{deal['ret_airline']} {deal['ret_flight_no']})*\n"
            msg += f"   시간: {deal['ret_dep_time']} ➔ {deal['ret_arr_time']}\n\n"

        send_telegram_msg(msg)
    else:
        print("\n결과: 지정한 조건(가격/시간대)을 모두 만족하는 항공권이 없습니다.")

if __name__ == "__main__":
    main()
