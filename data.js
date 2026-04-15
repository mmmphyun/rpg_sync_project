/**
 * Application Data Store
 * API 연동 전 임시 하드코딩 데이터 및 매핑 상수 정의
 */

const JOBS = [
    // 게이트 C [데몬]
    { name: "다크 메이지", gate: "게이트 C", group: "데몬", desc: "코드 데미안을 도와 게이트 C 데몬성을 다시 세우려는 인물입니다. 스태프나 완드를 주로 사용하는 딜 마법사입니다.", range: "원거리", position: "딜", resource: "모름", img: "다크메이지.png", photos: ["다크메이지1.jpg","다크메이지2.jpg","다크메이지3.jpg"] },
    { name: "진", gate: "게이트 C", desc: "반은 인간 반은 마족의 힘을 사용하며, 흡혈 계수가 높은 캐릭터입니다.", range: "근거리", position: "딜", resource: "모름", img: "진.png", photos: ["진1.jpg","진2.jpg"] },
  
    // 게이트 X, Z [그림자 단]
    { name: "카게노 엔디", gate: "게이트 X, Z", group: "그림자 단", desc: "거대한 낫을 주로 사용하는 근접 딜러입니다. 상황에 따라 무기를 변형하여 사용 가능한 근(원)거리 딜러.", range: "근거리", position: "딜", resource: "모름", img: "카게노엔디.png", photos: ["카게노엔디1.jpg","카게노엔디2.jpg"] },
    { name: "켄", gate: "게이트 X, Z", group: "그림자 단", desc: "단검을 사용하며, 높은 기동성과 딜의 한계가 높은 근거리 딜러입니다.", range: "근거리", position: "딜", resource: "모름", img: "", photos: [] },
    { name: "스모커", gate: "게이트 X, Z", group: "그림자 단", desc: "검을 주로 사용하는 근접 딜러입니다. (비밀이 숨겨진 직업입니다)", range: "근거리", position: "딜", resource: "기력", img: "스모커.png", photos: ["스모커1.jpg","스모커2.jpg","스모커3.jpg"], patches: [{date:"2026-04-06",notes:"고정데미지가 마법데미지로 변경\n지로화 사용시 끌어당기는 힘이 사라짐\n기력을 사용"}], players: ["곰돼지"] },
    { name: "카게노 스이치", gate: "게이트 X, Z", group: "그림자 단", desc: "검과 단검을 주로 사용하는 근접 딜러입니다. 그림자단 중에 고점이 가장 높습니다.", range: "근거리", position: "딜", resource: "모름", img: "카게노스이치.png", photos: ["카게노스이치1.jpg","카게노스이치2.jpg"] },
    { name: "카시우스", gate: "게이트 X, Z", group: "그림자 단", desc: "코드의 힘으로 되살아난 존재입니다. 거대한 둔기를 사용하는 근접 (탱)딜러.", range: "근거리", position: "딜", resource: "모름", img: "카시우스.png", photos: ["카시우스1.jpg","카시우스2.jpg","카시우스3.jpg","카시우스4.jpg"] },
    { name: "카게노 진", gate: "게이트 X, Z", group: "그림자 단", desc: "하데스의 사용자이자 전대 그림자단 수장. (1차 각성 계정 보유시 전직/직변 가능) 1차 각성부터 시작합니다.", range: "근거리", position: "딜", resource: "모름", img: "카게노진.png", photos: ["카게노진1.jpg","카게노진2.jpg","카게노진3.jpg"] },
    { name: "사토 덴지", gate: "게이트 X, Z", group: "그림자 단", desc: "검과 표창을 사용하며, 기동성과 고점이 높은 원거리 딜러입니다.", range: "원거리", position: "딜", resource: "모름", img: "사토덴지.png", photos: ["사토덴지1.jpg","사토덴지2.jpg"] },
    { name: "카게노 카시아", gate: "게이트 X, Z", group: "그림자 단", desc: "활 종류의 무기를 사용하고, 일반적인 원거리 딜러들보다 단단하며 기동성과 고점이 높은 원거리 딜러입니다.", range: "원거리", position: "딜", resource: "모름", img: "카시아.png", photos: ["카시아1.jpg","카시아2.jpg"], mobility: "있음" },
  
    // 게이트 X [??]
    { name: "엔도 세이지", gate: "게이트 X", group: "??", desc: "기력과 단검을 사용하는 근접(탱)딜러.", range: "근거리", position: "딜", resource: "기력", img: "엔도세이지.png", photos: ["엔도세이지1.jpg","엔도세이지2.jpg","엔도세이지3.jpg","엔도세이지4.jpg","엔도세이지5.jpg"], patches: [{date:"2026-04-06",notes:"체력보다 마나를 먼저 사용\n하이브리드 기능 추가\n세이지의 스킬이 아군에게 맞지 않음"}], players: ["지수","샤샤"] },
  
    // 게이트 A [십이지(十二支)]
    { name: "자(子)", gate: "게이트 A", group: "십이지(十二支)", desc: "부채를 사용하는 지지신.", range: "모름", position: "모름", resource: "모름", img: "", photos: [] },
    { name: "인(寅)", gate: "게이트 A", group: "십이지(十二支)", desc: "검을 사용하는 지지신.", range: "근거리", position: "모름", resource: "모름", img: "", photos: [] },
    { name: "묘(卯)", gate: "게이트 A", group: "십이지(十二支)", desc: "활을 사용하는 지지신.", range: "원거리", position: "모름", resource: "모름", img: "", photos: [] },
    { name: "진(辰)", gate: "게이트 A", group: "십이지(十二支)", desc: "검 종류를 사용하는 지지신.", range: "근거리", position: "모름", resource: "모름", img: "진(辰).png", photos: ["진(辰)1.jpg","진(辰)2.jpg"] },
    { name: "사(巳)", gate: "게이트 A", group: "십이지(十二支)", desc: "단검류를 사용하는 지지신.", range: "근거리", position: "모름", resource: "모름", img: "", photos: [] },
    { name: "오(午)", gate: "게이트 A", group: "십이지(十二支)", desc: "양손 둔기를 사용하는 지지신.", range: "근거리", position: "모름", resource: "모름", img: "", photos: [] },
    { name: "술(戌)", gate: "게이트 A", group: "십이지(十二支)", desc: "이도류를 사용하는 지지신.", range: "근거리", position: "모름", resource: "모름", img: "", photos: [] },
  
    // 환신 / 집시 / 금강
    { name: "김 신", gate: "모름", group: "환신", desc: "서버 내 1인 제한. 서버내 2차 각성한 계정 필요.", range: "모름", position: "모름", resource: "모름", img: "환신.png", photos: ["환신1.jpg","환신2.jpg"], limit: true },
    { name: "사토 집시", gate: "모름", group: "집시", desc: "서버 내 1인 제한. 서버 내 2차 각성 계정 필요.", range: "모름", position: "모름", resource: "모름", img: "사토집시.png", photos: ["사토집시1.jpg","사토집시2.jpg"], limit: true },
    { name: "금강", gate: "모름", group: "금강", desc: "요촌의 신선들 중 1명이며, 신선들 중 유일하게 요괴 전쟁에 참여했다.", range: "모름", position: "모름", resource: "모름", img: "금강.png", photos: ["금강1.jpg","금강2.jpg","금강3.jpg"] },
  
    // 게이트 B [케이브 행성]
    { name: "카덴", gate: "게이트 B", group: "케이브 행성", desc: "카이쿤의 소멸과 스이치의 영향으로 만들어진 케이지, 전사.", range: "근거리", position: "딜", resource: "모름", img: "카덴.png", photos: ["카덴1.jpg","카덴2.jpg"], patches: [{date:"2026-02-11",notes:"빛의 길 이동거리 증가\n검 데미지 증가 + 흡혈력 /2"}] },
    { name: "카린", gate: "게이트 B", group: "케이브 행성", desc: "카이쿤의 소멸과 스이치의 영향으로 만들어진 케이주, 원거리 딜러.", range: "원거리", position: "딜", resource: "모름", img: "카린.png", photos: ["카린1.jpg","카린2.jpg"] },
  
    // 게이트 L [파괴된 게이트]
    { name: "샤크", gate: "게이트 L", group: "파괴된 게이트", desc: "게이트 폭발에 휘말려 데몬의 힘으로 되살아난 괴물입니다. 코드를 보유하고 있으며 코드의 힘을 사용합니다.", range: "모름", position: "딜/탱", resource: "모름", img: "샤크.png", photos: ["샤크1.jpg","샤크2.jpg","샤크3.jpg","샤크4.jpg"] },
  
    // 게이트 S
    { name: "아오이 진", gate: "게이트 S", desc: "마나를 사용하는 검사입니다. 근접 딜러. (서버내 1인 제한)", range: "근거리", position: "딜", resource: "마나", img: "아오이진.png", photos: ["아오이진1.jpg","아오이진2.jpg","아오이진3.jpg"], limit: true },
  
    // 게이트 M
    { name: "이가라시 슈헤이", gate: "게이트 M", desc: "기력을 사용하는 근접 딜러.", range: "근거리", position: "딜", resource: "기력", img: "슈헤이.png", photos: ["슈헤이1.jpg","슈헤이2.jpg","슈헤이3.jpg","슈헤이4.jpg"], players: ["나나"] },
    { name: "이가라시 유키", gate: "게이트 M", desc: "기력을 사용하는 암살 딜러.", range: "근거리", position: "딜", resource: "기력", img: "유키.png", photos: ["유키1.jpg","유키2.jpg","유키3.jpg","유키4.jpg"] },
    { name: "이가라시 미츠키", gate: "게이트 M", desc: "체력을 사용하는 탱 딜러.", range: "근거리", position: "탱", resource: "체력", img: "미츠키.png", photos: ["미츠키1.jpg","미츠키2.jpg","미츠키3.jpg"] },
    { name: "츠키요미 세이렌", gate: "게이트 M", desc: "기력을 사용하며, 인술과 체술을 사용하는 닌자. 근접 딜러.", range: "근거리", position: "딜", resource: "기력", img: "츠미요미세이렌.png", photos: ["츠키요미세이렌1.jpg","츠키요미세이렌2.jpg","츠키요미세이렌3.jpg"], players: ["태태"] },
  
    // 게이트 Z
    { name: "사토 신지", gate: "게이트 Z", desc: "사토 가문의 먼 후예. 기계 장치를 사용하는 근/원거리 딜러.", range: "근거리", position: "딜", resource: "모름", img: "사토신지.png", photos: ["사토신지1.jpg","사토신지2.jpg"], patches: [{date:"2026-01-31",notes:"공격 사거리 감소\n스킬 사용시 에너지 소모량 증가"},{date:"2026-02-11",notes:"기본공격 사거리 증가\n스킬 사용시 체력 사용 삭제\n하이브리드 기능 추가"}] },
    { name: "사토 하야테", gate: "게이트 Z", desc: "사토 7검의 후예. 검과 총기를 사용하는 근/원거리 딜러.", range: "근거리", position: "딜", resource: "모름", img: "사토하야테.png", photos: ["사토하야테1.jpg","사토하야테2.jpg"] },
    { name: "카게노 미오", gate: "게이트 Z", desc: "카게노 가문의 먼 후예. 거대한 낫을 사용하는 근(원)거리 딜러.", range: "근거리", position: "딜", resource: "모름", img: "카게노미오.png", photos: ["카게노미오1.jpg","카게노미오2.jpg","카게노미오3.jpg","카게노미오4.jpg"] },
    { name: "베라", gate: "게이트 Z", desc: "저격 총을 사용하는 원거리 딜러.", range: "원거리", position: "딜", resource: "모름", img: "베라.png", photos: ["베라1.jpg","베라2.jpg"] },
    { name: "유나", gate: "게이트 Z", desc: "이동기가 다양한 근접 딜러, 무투가.", range: "근거리", position: "유틸", resource: "모름", img: "유나.png", photos: ["유나1.jpg","유나2.jpg","유나3.jpg"], mobility: "있음", patches: [{date:"2026-02-11",notes:"힐량 증가\n새로운 스킬 아군 전체 회복 기능 추가"}] },
    { name: "제리", gate: "게이트 Z", desc: "비밀이 숨겨진 직업. 근접 딜러: 무투가, 전사.", range: "근거리", position: "딜", resource: "모름", img: "제리.png", photos: ["제리1.jpg","제리2.jpg"], patches: [{date:"2026-02-11",notes:"궁극기 사용시 3초에 한번 체력 감소 (최대 5회) / 힘 버프 7→5 60초\n낙뢰 이동경로 변경"}] },
    { name: "히데", gate: "게이트 Z", desc: "방패를 사용하며 높은 방어력 CC기를 활용하여 아군을 보호, 서포터하는 탱커.", range: "근거리", position: "탱", resource: "모름", img: "히데.png", photos: ["히데1.jpg","히데2.jpg"] },
    { name: "엠버", gate: "게이트 Z", desc: "게이트 E에서 생산된 보급형 가이노이드. 전문 힐러 서포터.", range: "모름", position: "힐", resource: "모름", img: "엠버.png", photos: ["엠버1.jpg","엠버2.jpg","엠버3.jpg"] },
    { name: "파이로", gate: "게이트 Z", desc: "게이트 E에서 코드 과주입으로 생성된 전투형 안드로이드.", range: "모름", position: "딜", resource: "모름", img: "파이로.png", photos: ["파이로1.jpg","파이로2.jpg","파이로3.jpg","파이로4.jpg","파이로5.jpg"] },
  
    // 게이트 G [자이언]
    { name: "바움", gate: "게이트 G", group: "자이언", desc: "단단한 몸과 높은 체력을 자랑하며 유지력이 좋은 탱커.", range: "근거리", position: "탱", resource: "모름", img: "바움.png", photos: ["바움1.jpg","바움2.jpg"], patches: [{date:"2026-01-26",notes:"궁극기 사용시 체력 회복이 삭제\n스킬 사용시 소모되는 체력이 높아짐\n저항 레벨이 낮아짐"}] },
    { name: "즈윌링", gate: "게이트 G", group: "자이언", desc: "두 가지 무기를 사용 가능하며, 코드를 사용하며 전투하는 근접 딜러. 전사.", range: "근거리", position: "딜", resource: "모름", img: "즈윌링.png", photos: ["즈윌링1.jpg","즈윌링2.jpg","즈윌링3.jpg","즈윌링4.jpg"], patches: [{date:"2026-02-11",notes:"묵직한 검 유지 시간 증가\n묵직한 검 소모 마나량 감소\n묵직한 검 소모 체력 감소"}], players: ["제라"] },
    { name: "소네", gate: "게이트 G", group: "자이언", desc: "사거리가 긴 게 특징인 원거리 마법사. (딜러/힐러 각성 가능)", range: "원거리", position: "딜", resource: "모름", img: "소네.png", photos: ["소네1.jpg","소네2.jpg"], mobility: "없음", patches: [{date:"2026-01-26",notes:"고정 힐 수치 감소\n스킬 사용시 필요 체력/마나 증가\n기본 공격 사거리 감소\n기본 공격 사용시 마나 소모"}] },
    { name: "스구라", gate: "게이트 G", group: "자이언", desc: "전설의 7대 검사 중 한 명. 자이언 부족. (요괴 전쟁 참여) 근접 딜러.", range: "근거리", position: "딜", resource: "모름", img: "스구라.png", photos: ["스구라1.jpg","스구라2.jpg","스구라3.jpg"] },
    { name: "퓨어", gate: "게이트 G", group: "자이언", desc: "대검을 사용하는 자이언 부족의 서브 딜러.", range: "근거리", position: "딜", resource: "모름", img: "퓨어.png", photos: ["퓨어1.jpg","퓨어2.jpg"] },
    { name: "라일라", gate: "게이트 G", group: "자이언", desc: "자이언 부족의 메인 힐러.", range: "모름", position: "힐", resource: "마나", img: "라일라.png", photos: ["라일라1.jpg","라일라2.jpg"] },
  
    // 게이트 N
    { name: "지로", gate: "게이트 N", desc: "미케의 자식, 다섯 수호신 중 하나. 마법딜/탱. (서버 내 초월한 계정 필요)", range: "원거리", position: "딜/탱", resource: "모름", img: "지로.png", photos: ["지로1.jpg","지로2.jpg","지로3.jpg"], players: ["포동"] },
    { name: "키리", gate: "게이트 N", desc: "사거리가 긴 근/원거리 닌자, 자객. (현재 전직 불가)", range: "근거리", position: "딜", resource: "모름", img: "키리.png", photos: ["키리1.jpg","키리2.jpg","키리3.jpg","키리4.jpg","키리5.jpg"] },
    { name: "사키", gate: "게이트 N", desc: "사거리가 긴 근/원거리 닌자, 자객.", range: "근거리", position: "딜", resource: "기력", img: "사키.png", photos: ["사키1.jpg","사키2.jpg"], patches: [{date:"2026-01-31",notes:"그림자의 길 체력 소모량 증가\n그림자의 길 지속시간 1초 감소"},{date:"2026-02-11",notes:"그림자의 길 사용시 체력 재생\n기본 공격 적중시 치명타 확률 증가 (최대 5%)\n기본 공격 표창 수 증가 2→3"},{date:"2026-02-13",notes:"체력 → 기력을 사용\n하이브리드 기능 추가"}] },
    { name: "이리아", gate: "게이트 N", desc: "귀족 출신의 활을 사용하는 원거리 자객.", range: "원거리", position: "딜", resource: "모름", img: "이리아.png", photos: ["이리아1.jpg","이리아2.jpg","이리아3.jpg"] },
    { name: "사토 카게", gate: "게이트 N", desc: "사토 가문의 7대 검사 중 한 명으로 기력을 사용합니다. (요괴 전쟁 참여)", range: "근거리", position: "딜", resource: "기력", img: "사토카게.png", photos: ["사토카게1.jpg","사토카게2.jpg","사토카게3.jpg"], players: ["칸쵸"] },
    { name: "사토 키도", gate: "게이트 N", desc: "사토 가문의 7대 검사 중 한 명으로 기력을 사용합니다. (요괴 전쟁 참여)", range: "근거리", position: "딜", resource: "기력", img: "사토기도.png", photos: ["사토기도1.jpg","사토기도2.jpg","사토기도3.jpg","사토기도4.jpg"] },
    { name: "아카토라 시구야", gate: "게이트 N", desc: "아카토라 일족의 야생성을 추구하며 기력을 사용하는 근접 (탱)딜러/전사.", range: "근거리", position: "딜", resource: "기력", img: "아카토라시구야.png", photos: ["아카토라시구야1.jpg","아카토라시구야2.jpg","아카토라시구야3.jpg"] },
    { name: "사토 시로아키", gate: "게이트 N", desc: "전설의 7대 검사 중 한 명으로 도끼와 검을 주로 사용하는 근접 전사. 기력을 사용합니다.", range: "근거리", position: "딜", resource: "기력", img: "사토시로야키.png", photos: ["사토시로아키1.jpg","사토시로아키2.jpg","사토시로아키3.jpg","사토시로아키4.jpg"] },
    { name: "쿠로야기", gate: "게이트 N", desc: "쿠로야기 가문의 초대 수장으로, 바람과 번개 그리고 수호신의 힘을 사용하는 검사입니다. 기력을 사용합니다.", range: "근거리", position: "딜", resource: "기력", img: "쿠로야기.png", photos: ["쿠로야기1.jpg","쿠로야기2.jpg","쿠로야기3.jpg","쿠로야기4.jpg","쿠로야기5.jpg","쿠로야기6.jpg"] },
    { name: "쿠로야기 렌", gate: "게이트 N", desc: "쿠로야기 가문의 근접 딜러(검사). 기력을 사용하는 사무라이입니다.", range: "근거리", position: "딜", resource: "기력", img: "쿠로야기렌.png", photos: ["쿠로야기렌1.jpg","쿠로야기렌2.jpg","쿠로야기렌3.jpg","쿠로야기렌4.jpg"] },
    { name: "쿠로야기 젠", gate: "게이트 N", desc: "쿠로야기 가문의 근접 딜러(검사). 기력을 사용하는 사무라이입니다.", range: "근거리", position: "딜", resource: "기력", img: "쿠로야기젠.png", photos: ["쿠로야기젠1.jpg","쿠로야기젠2.jpg","쿠로야기젠3.jpg"] },
    { name: "쿠로야기 타츠야", gate: "게이트 N", desc: "쿠로야기 가문의 근거리 딜러(암살자). 기력을 사용하는 사무라이.", range: "근거리", position: "딜", resource: "기력", img: "쿠로야기타츠야.png", photos: ["쿠로야기타츠야1.jpg","쿠로야기타츠야2.jpg","쿠로야기타츠야3.jpg"] },
    { name: "메구미", gate: "게이트 N", desc: "정체 모를 암살단원. 근접 극딜러. (비밀이 숨겨진 직업입니다)", range: "근거리", position: "딜", resource: "모름", img: "메구미.png", photos: ["메구미1.jpg","메구미2.jpg","메구미3.jpg"], players: ["꼰듀"] },
  
    // 게이트 E
    { name: "벨룸", gate: "게이트 E", desc: "벤의 공장에서 코드 실험체로 만들어진 괴수.", range: "모름", position: "모름", resource: "모름", img: "벨룸.png", photos: ["벨룸1.jpg","벨룸2.jpg"] },
  
    // 게이트 V
    { name: "바륵", gate: "게이트 V", desc: "게이트 E에서 탈출한 실험체 괴수-4. 기력을 사용합니다.", range: "모름", position: "모름", resource: "기력", img: "바륵.png", photos: ["바륵1.jpg","바륵2.jpg","바륵3.jpg"] },
    { name: "브리지", gate: "게이트 V", desc: "게이트 E에서 흘러나온 독성 물질이 합쳐져 만들어진 괴수-6. 체력을 사용합니다.", range: "모름", position: "모름", resource: "모름", img: "브리지.png", photos: ["브리지1.jpg","브리지2.jpg"] },
    { name: "타르", gate: "게이트 V", desc: "쿠쿠가 만든 최고의 실패작. 체력을 사용합니다. E-12.", range: "모름", position: "모름", resource: "모름", img: "타르.png", photos: ["타르1.jpg","타르2.jpg"] },
    { name: "예거", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 소총을 사용하며 새로운 자원을 사용합니다.", range: "원거리", position: "딜", resource: "모름", img: "예거.png", photos: ["예거1.jpg","예거2.jpg"] },
    { name: "멧", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 샷건을 사용하며 새로운 자원을 사용합니다.", range: "원거리", position: "딜", resource: "모름", img: "멧.png", photos: ["멧1.jpg","멧2.jpg","멧3.jpg"], patches: [{date:"2026-02-11",notes:"12게이지 탄창 증가 20→30\n기본공격 총알 발사 수 증가 2→4\n기본공격시 소모되는 총알 감소 2→1"}] },
    { name: "프레이", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 낫과 도끼를 사용하며 기력을 사용합니다.", range: "근거리", position: "딜", resource: "기력", img: "프레이.png", photos: ["프레이1.jpg","프레이2.jpg","프레이3.jpg"] },
    { name: "스톤", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 검과 창을 사용하며 마나를 사용합니다. 과거 게이트 폭발에서 살아남은 전적이 있습니다.", range: "근거리", position: "딜", resource: "마나", img: "스톤.png", photos: ["스톤1.jpg","스톤2.jpg"], patches: [{date:"2026-02-11",notes:"궁극기 사용시 최대 체력 증가\n궁극기 패시브 체력 회복량 감소\n궁극기 사용시 저항 1 /15초"}] },
    { name: "리트", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 단검과 카타나, 표창을 사용하며 기력을 사용합니다.", range: "근거리", position: "딜", resource: "기력", img: "리트.png", photos: ["리트1.jpg","리트2.jpg","리트3.jpg","리트4.jpg"] },
    { name: "레나", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 망치와 둔기를 사용하며 새로운 자원을 사용합니다.", range: "근거리", position: "딜", resource: "모름", img: "레나.png", photos: ["레나1.jpg","레나2.jpg","레나3.jpg"] },
    { name: "사토 시로", gate: "게이트 V", group: "포레스트", desc: "괴수 사냥꾼. 사토 가문에서 탈주. 기력을 사용합니다.", range: "근거리", position: "딜", resource: "기력", img: "사토시로.png", photos: ["사토시로1.jpg","사토시로2.jpg","사토시로3.jpg"] },
  
    // 고대 게이트
    { name: "레이지", gate: "고대 게이트", desc: "검을 사용하는 근접 전사. 분노.", range: "근거리", position: "딜", resource: "마나", img: "레이지.png", photos: ["레이지1.jpg"] },
    { name: "코벳", gate: "고대 게이트", desc: "둔기를 사용하는 근접 탱 딜러. 탐욕.", range: "근거리", position: "딜", resource: "마나", img: "코벳.png", photos: ["코벳1.jpg","코벳2.jpg"] },
    { name: "젤러시", gate: "고대 게이트", desc: "단검을 주로 사용하는 근거리 딜러. 질투.", range: "근거리", position: "딜", resource: "기력", img: "젤러시.png", photos: ["젤러시1.jpg"] },
];
  
// UI Class Mappings
const RANGE_CLS = { "근거리": "t-melee", "원거리": "t-ranged", "정보 없음": "t-unknown" };
const POS_CLS   = { "탱": "t-tank", "딜": "t-deal", "힐": "t-heal", "유틸": "t-util", "정보 없음": "t-unknown" };
const RES_CLS   = { "기력": "t-ki", "마나": "t-mana", "체력": "t-hp", "없음": "t-none", "정보 없음": "t-unknown" };
const POS_BG    = { "탱": "bg-tank", "딜": "bg-deal", "힐": "bg-heal", "유틸": "bg-util", "정보 없음": "bg-unknown" };
const BOOL_CLS  = { "있음": "t-yes", "없음": "t-no", "정보 없음": "t-unknown" };