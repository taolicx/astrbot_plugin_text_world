from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DefaultLocation:
    id: str
    name: str
    description: str
    neighbors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class DefaultNPC:
    id: str
    name: str
    role: str
    location_id: str
    disposition: str = "中立"
    faction: str = ""
    memory: str = ""
    schedule_hint: str = ""


@dataclass
class DefaultShopItem:
    name: str
    description: str
    price: int
    effect: dict[str, Any] = field(default_factory=dict)
    stock: int = -1


@dataclass
class DefaultEventPreset:
    title: str
    description: str
    effect: dict[str, Any] = field(default_factory=dict)


CHARACTER_CARD_TEMPLATE = """创建角色 游戏名 | 身份 | 阵营 | 能力 | 能力等级

也可以直接自然语言提交，例如：
创建角色 我叫星野遥，是第七学区某高中学生兼风纪委员见习，能力是微弱电磁感应，Level 2。

字段说明：
- 游戏名：前端登录账号也会默认使用这个名字。
- 身份：第七学区某高中学生、栅川中学学生、风纪委员见习、警备员协助者、研究所实习生、留学生、Skill-Out边缘成员等。
- 阵营：普通学生、风纪委员 Judgment、警备员 Anti-Skill、研究机构、Skill-Out、暗部边缘、留学生、魔法侧访客、无阵营等。
- 能力：按学园都市“个人现实/AIM扩散力场”的超能力体系写清表现、限制和代价；通常一名能力者只有一种主能力。
- 能力等级：Level 0 / Level 1 / Level 2 / Level 3 / Level 4。Level 5 属于学园都市仅七人的顶级超能力者，建议只允许管理员特批；Level 6/绝对能力者禁止创建。

示例：
创建角色 星野遥 | 第七学区某高中学生，风纪委员见习 | 风纪委员 Judgment | 微弱电磁感应，可察觉近距离异常电流，连续使用会头痛 | Level 2
"""


DEFAULT_LOCATIONS: dict[str, DefaultLocation] = {
    "school_gate": DefaultLocation(
        id="school_gate",
        name="第七学区某高中校门",
        description="上条当麻就读的某高中周边。公告栏、校车站和学生通勤人流密集，是普通学生最自然的行动起点。",
        neighbors=["district_07", "main_road", "classroom", "dorm", "futsukaichi_station"],
        tags=["第七学区", "学校", "交通", "起点"],
    ),
    "main_road": DefaultLocation(
        id="main_road",
        name="第七学区生活圈主干道",
        description="连接某高中、学生寮、二日站、Seventh Mist、医院和风纪委员支部的日常道路，警备机器人与校车频繁经过。",
        neighbors=["school_gate", "district_07", "plaza", "hospital", "futsukaichi_station", "seventh_mist", "judgment_177"],
        tags=["第七学区", "公共", "交通"],
    ),
    "classroom": DefaultLocation(
        id="classroom",
        name="上条的高中",
        description="第七学区的普通高中。能力开发课程、补习、社团传闻和学生日常都从这里开始。",
        neighbors=["school_gate", "library", "plaza", "dorm", "family_restaurant"],
        tags=["第七学区", "学校", "学习"],
    ),
    "library": DefaultLocation(
        id="library",
        name="校内资料室与书库公开终端",
        description="只能查询公开等级资料的资料室。涉及研究所、暗部、滞空回线等高权限情报时，通常只会得到残缺线索。",
        neighbors=["classroom", "plaza", "judgment_177", "district_18"],
        tags=["第七学区", "情报", "学习"],
    ),
    "lab": DefaultLocation(
        id="lab",
        name="研究所外围登记处",
        description="连接水穗机构与S Processor等研究设施的外围登记处。普通玩家只能接触公开入口、访客窗口和封锁线外侧。",
        neighbors=["hospital", "mizuho_pathology", "s_processor", "district_02", "district_18"],
        tags=["第七学区", "研究", "能力开发", "高风险"],
    ),
    "dorm": DefaultLocation(
        id="dorm",
        name="第七学区学生寮",
        description="学生生活区。休息、串门、小交易、补课通知和深夜传闻都常在这里发生。",
        neighbors=["school_gate", "classroom", "canteen", "plaza", "family_restaurant"],
        tags=["第七学区", "生活", "休息"],
    ),
    "canteen": DefaultLocation(
        id="canteen",
        name="学生寮食堂",
        description="面向学生营业的普通食堂，与第四学区食品供应链相连，适合补充水分和饱食度。",
        neighbors=["dorm", "market", "family_restaurant", "district_04"],
        tags=["生活", "消费", "食物"],
    ),
    "market": DefaultLocation(
        id="market",
        name="第七学区商业入口",
        description="通往Seventh Mist、七福神商店街和便利店街区的商业入口。日用品、电子产品和都市传说都容易在这里汇集。",
        neighbors=["district_15", "canteen", "plaza", "seventh_mist", "shichifukujin_street", "district_04"],
        tags=["第七学区", "消费", "情报", "商场"],
    ),
    "plaza": DefaultLocation(
        id="plaza",
        name="第七学区公共广场",
        description="学生集合、公开活动、偶遇、新闻屏幕和都市传说最容易交汇的开放空间。",
        neighbors=["main_road", "library", "canteen", "market", "shichifukujin_street", "district_07"],
        tags=["第七学区", "公共", "事件"],
    ),
    "hospital": DefaultLocation(
        id="hospital",
        name="冥土追魂所在医院",
        description="第七学区内由“冥土追魂”坐镇的医院。重伤治疗、健康检查、异常医学事件和保密病历都可能发生。",
        neighbors=["main_road", "lab", "anti_skill_07_hq", "district_07"],
        tags=["第七学区", "医疗", "恢复"],
    ),
    "gakusha_no_sono": DefaultLocation(
        id="gakusha_no_sono",
        name="学舍之园",
        description="第七学区内由多所贵族女校组成的封闭校区，常盘台中学也在其中。进入需要许可或邀请。",
        neighbors=["district_07", "tokiwa_dai", "seventh_mist"],
        tags=["第七学区", "学校", "封闭校区", "权限"],
    ),
    "tokiwa_dai": DefaultLocation(
        id="tokiwa_dai",
        name="常盘台中学",
        description="学舍之园内的顶级贵族女校，拥有御坂美琴、食蜂操祈等高等级能力者相关传闻。",
        neighbors=["gakusha_no_sono", "sakugawa", "district_18"],
        tags=["第七学区", "名校", "Level 5", "权限"],
    ),
    "sakugawa": DefaultLocation(
        id="sakugawa",
        name="栅川中学",
        description="初春饰利与佐天泪子就读的普通中学，适合日常线索、学生传闻和风纪委员支部事件切入。",
        neighbors=["tokiwa_dai", "judgment_177", "plaza"],
        tags=["第七学区", "学校", "日常"],
    ),
    "futsukaichi_station": DefaultLocation(
        id="futsukaichi_station",
        name="地下铁二日站",
        description="第七学区重要交通节点。适合跨区移动、跟踪、错过末班车和公共事件集合。",
        neighbors=["school_gate", "main_road", "district_15", "district_22", "district_23"],
        tags=["第七学区", "交通", "地铁"],
    ),
    "seventh_mist": DefaultLocation(
        id="seventh_mist",
        name="Seventh Mist",
        description="第七学区大型综合商场。购物、兼职、失物、学生约会和突发骚动都容易发生。",
        neighbors=["market", "main_road", "gakusha_no_sono", "shichifukujin_street"],
        tags=["第七学区", "商场", "消费", "公共"],
    ),
    "family_restaurant": DefaultLocation(
        id="family_restaurant",
        name="家庭餐厅",
        description="第七学区学生常去的家庭餐厅。适合低风险会面、打听公开传闻、恢复心情和补充饱食度。",
        neighbors=["classroom", "dorm", "canteen", "shichifukujin_street"],
        tags=["第七学区", "餐饮", "会面"],
    ),
    "shichifukujin_street": DefaultLocation(
        id="shichifukujin_street",
        name="七福神商店街",
        description="第七学区旧式商店街，日用品、便当、街坊传闻和小型委托比大型商场更接地气。",
        neighbors=["market", "plaza", "seventh_mist", "family_restaurant"],
        tags=["第七学区", "商店街", "消费", "传闻"],
    ),
    "anti_skill_07_hq": DefaultLocation(
        id="anti_skill_07_hq",
        name="警备员第七学区本部",
        description="警备员 Anti-Skill 的第七学区据点。报案、封锁线、训练委托和学生安全事件都从这里扩散。",
        neighbors=["hospital", "judgment_177", "main_road", "district_02"],
        tags=["第七学区", "警备员", "秩序"],
    ),
    "judgment_177": DefaultLocation(
        id="judgment_177",
        name="风纪委员活动第177支部",
        description="风纪委员 Judgment 的常见支部之一，适合失物、巡逻、学生纠纷和公开情报检索。",
        neighbors=["main_road", "library", "sakugawa", "anti_skill_07_hq"],
        tags=["第七学区", "风纪委员", "秩序", "情报"],
    ),
    "windowless_building": DefaultLocation(
        id="windowless_building",
        name="没有窗户的大楼",
        description="亚雷斯塔相关传闻的核心禁区。普通角色只能远望或听到流言，不能直接闯入。",
        neighbors=["district_07", "anti_skill_07_hq"],
        tags=["第七学区", "统括理事会", "禁区", "高风险"],
    ),
    "mizuho_pathology": DefaultLocation(
        id="mizuho_pathology",
        name="水穗机构・病理解析研究所",
        description="与御坂妹妹相关实验传闻相连的研究设施。适合调查外围、文件碎片和警备封锁事件。",
        neighbors=["lab", "s_processor", "district_18"],
        tags=["第七学区", "研究所", "暗线", "高风险"],
    ),
    "s_processor": DefaultLocation(
        id="s_processor",
        name="S Processor 脑神经应用分析所",
        description="与脑神经、能力开发和实验数据相关的研究设施。普通行动只能触及公开入口或外围异常。",
        neighbors=["lab", "mizuho_pathology", "district_18"],
        tags=["第七学区", "研究所", "能力开发", "高风险"],
    ),
    "district_01": DefaultLocation(
        id="district_01",
        name="第一学区（司法行政区）",
        description="司法、行政与统括理事会相关机构集中的政府街，权限审查严格。",
        neighbors=["district_02", "district_03", "district_07", "district_12"],
        tags=["行政", "司法", "统括理事会"],
    ),
    "district_02": DefaultLocation(
        id="district_02",
        name="第二学区（警备训练区）",
        description="警备员与风纪委员训练机构、新武器开发设施所在，噪音和演习较多。",
        neighbors=["district_01", "district_07", "district_17", "lab"],
        tags=["警备员", "风纪委员", "军事", "训练"],
    ),
    "district_03": DefaultLocation(
        id="district_03",
        name="第三学区（外交展示区）",
        description="对外展示设施、住宿条件和外部来访窗口集中，是学园都市的外交门面。",
        neighbors=["district_01", "district_11", "district_14", "district_23"],
        tags=["外交", "酒店", "展示"],
    ),
    "district_04": DefaultLocation(
        id="district_04",
        name="第四学区（餐饮与农业大楼）",
        description="食品店、世界料理和农业大楼密集，能买到大量日常补给。",
        neighbors=["district_05", "district_15", "canteen", "market"],
        tags=["餐饮", "农业大楼", "补给"],
    ),
    "district_05": DefaultLocation(
        id="district_05",
        name="第五学区（大学区）",
        description="大学、高级店铺和成人设施较多，学术讲座与研究委托常在此流转。",
        neighbors=["district_04", "district_06", "district_18"],
        tags=["大学", "研究", "成人设施"],
    ),
    "district_06": DefaultLocation(
        id="district_06",
        name="第六学区（娱乐休闲区）",
        description="以娱乐设施为主的休闲学区，活动丰富，也容易混入可疑传单。",
        neighbors=["district_05", "district_07", "district_20"],
        tags=["娱乐", "活动", "休闲"],
    ),
    "district_07": DefaultLocation(
        id="district_07",
        name="第七学区（中心学区）",
        description="学园都市中心，也是《魔禁/超炮》主要舞台。上条的高中、学舍之园、常盘台中学、栅川中学、冥土追魂医院、无窗大楼等关键地点都在这里交汇。",
        neighbors=[
            "school_gate",
            "main_road",
            "plaza",
            "hospital",
            "gakusha_no_sono",
            "tokiwa_dai",
            "sakugawa",
            "futsukaichi_station",
            "seventh_mist",
            "family_restaurant",
            "shichifukujin_street",
            "anti_skill_07_hq",
            "judgment_177",
            "windowless_building",
            "mizuho_pathology",
            "s_processor",
            "district_01",
            "district_02",
            "district_06",
            "district_08",
            "district_15",
            "district_18",
            "district_22",
            "district_23",
        ],
        tags=["中心", "学校", "医院", "交通"],
    ),
    "district_08": DefaultLocation(
        id="district_08",
        name="第八学区（教师住宿区）",
        description="教师住宿与教育设施集中，古街道和新建筑交错，气氛比中心区安静。",
        neighbors=["district_07", "district_09", "district_13"],
        tags=["教师", "住宿", "教育"],
    ),
    "district_09": DefaultLocation(
        id="district_09",
        name="第九学区（工艺美术区）",
        description="工艺、美术和特殊教育设施集中，适合艺术类委托与制作道具。",
        neighbors=["district_08", "district_10", "district_20"],
        tags=["艺术", "工艺", "制作"],
    ),
    "district_10": DefaultLocation(
        id="district_10",
        name="第十学区（墓地与少年院）",
        description="地价最低的学区，墓地、少年院和高风险设施并存，都市阴影较重。",
        neighbors=["district_09", "district_11", "district_19"],
        tags=["少年院", "墓地", "危险"],
    ),
    "district_11": DefaultLocation(
        id="district_11",
        name="第十一学区（陆路物流口）",
        description="学园都市陆路最大玄关口，物流车队、货检与外界边界都在此出现。",
        neighbors=["district_03", "district_10", "district_17", "district_23"],
        tags=["物流", "边界", "交通"],
    ),
    "district_12": DefaultLocation(
        id="district_12",
        name="第十二学区（宗教与神学研究区）",
        description="分布宗教设施和以科学研究神学的学校，异国气氛浓厚。",
        neighbors=["district_01", "district_13", "district_14"],
        tags=["宗教", "神学", "异国"],
    ),
    "district_13": DefaultLocation(
        id="district_13",
        name="第十三学区（幼小教育区）",
        description="幼儿园与小学为主，治安相对较好，但儿童能力开发相关传闻不少。",
        neighbors=["district_08", "district_12", "district_14"],
        tags=["小学", "幼儿园", "治安"],
    ),
    "district_14": DefaultLocation(
        id="district_14",
        name="第十四学区（留学生区）",
        description="海外留学生众多，街头有多语种告示牌，外部文化与学都规则在此碰撞。",
        neighbors=["district_03", "district_12", "district_13", "district_15"],
        tags=["留学生", "多语言", "交流"],
    ),
    "district_15": DefaultLocation(
        id="district_15",
        name="第十五学区（商业与媒体中心）",
        description="学园都市最大的商业中心，电视台、大众传媒和大型屏幕密集。",
        neighbors=["district_04", "district_07", "district_14", "district_16", "market"],
        tags=["商业", "媒体", "消费"],
    ),
    "district_16": DefaultLocation(
        id="district_16",
        name="第十六学区（学生打工区）",
        description="学生兼职设施集中，适合打工、跑腿和小额委托。",
        neighbors=["district_04", "district_15", "district_17"],
        tags=["打工", "兼职", "委托"],
    ),
    "district_17": DefaultLocation(
        id="district_17",
        name="第十七学区（工业制造区）",
        description="工业制品制造工厂与高度机械化设施集中，也有高等级监狱传闻。",
        neighbors=["district_02", "district_11", "district_16", "district_19"],
        tags=["工业", "工厂", "监狱"],
    ),
    "district_18": DefaultLocation(
        id="district_18",
        name="第十八学区（能力开发名校区）",
        description="雾丘女学院、长点上机学园等名校和附属研究机构集中，优等生很多。",
        neighbors=["district_05", "district_07", "district_21", "classroom", "library", "lab", "tokiwa_dai", "mizuho_pathology", "s_processor"],
        tags=["名校", "能力开发", "研究"],
    ),
    "district_19": DefaultLocation(
        id="district_19",
        name="第十九学区（再开发失败区）",
        description="再开发失败后沉寂的荒凉学区，废弃建筑和可疑交易传闻较多。",
        neighbors=["district_10", "district_17", "district_20"],
        tags=["废弃", "危险", "传闻"],
    ),
    "district_20": DefaultLocation(
        id="district_20",
        name="第二十学区（运动工学区）",
        description="运动工学相关学校与学园都市运动协会本部所在地。",
        neighbors=["district_06", "district_09", "district_19", "district_21"],
        tags=["运动", "工学", "训练"],
    ),
    "district_21": DefaultLocation(
        id="district_21",
        name="第二十一学区（水源与山岳区）",
        description="全域水源、工业用水、水库、山岳和天文台所在，少见自然地貌保留较多。",
        neighbors=["district_18", "district_20", "district_22"],
        tags=["水源", "山岳", "天文台"],
    ),
    "district_22": DefaultLocation(
        id="district_22",
        name="第二十二学区（地下街区）",
        description="面积最小但地下高度发达，复杂地下街和垂直轴风力设施构成迷宫般空间。",
        neighbors=["district_07", "district_21", "district_23"],
        tags=["地下街", "能源", "复杂"],
    ),
    "district_23": DefaultLocation(
        id="district_23",
        name="第二十三学区（航空宇宙区）",
        description="航空、宇宙产业特化学区，拥有学园都市唯一机场。",
        neighbors=["district_03", "district_07", "district_11", "district_22"],
        tags=["机场", "航空", "宇宙"],
    ),
}


DEFAULT_NPCS: dict[str, DefaultNPC] = {
    "kamijou_touma": DefaultNPC(
        id="kamijou_touma",
        name="上条当麻",
        role="第七学区某高中学生，右手寄宿着可消除异能之力的“幻想杀手”。",
        faction="普通学生",
        location_id="classroom",
        disposition="热心",
        memory="会卷入麻烦并帮助弱者，但不会替玩家解决所有问题；涉及魔法侧时只留下克制线索。",
        schedule_hint="上课日多在某高中、学生寮和家庭餐厅附近。",
    ),
    "misaka_mikoto": DefaultNPC(
        id="misaka_mikoto",
        name="御坂美琴",
        role="常盘台中学学生，学园都市第三位 Level 5，能力名“超电磁炮”。",
        faction="常盘台中学",
        location_id="tokiwa_dai",
        disposition="爽快",
        memory="讨厌伤害无辜者的实验和事件，愿意帮忙处理公开层面的学生危机。",
        schedule_hint="常在常盘台、Seventh Mist、栅川中学周边行动。",
    ),
    "judgment_support": DefaultNPC(
        id="judgment_support",
        name="初春饰利",
        role="风纪委员支部的情报支援，擅长公开网络与书库终端检索。",
        faction="风纪委员 Judgment",
        location_id="judgment_177",
        disposition="友好",
        memory="会提醒玩家不要越权调查，也会提供公开情报、失物线索和支部委托。",
    ),
    "judgment_teleporter": DefaultNPC(
        id="judgment_teleporter",
        name="白井黑子",
        role="常盘台中学学生兼风纪委员，Level 4空间移动能力者。",
        faction="风纪委员 Judgment",
        location_id="judgment_177",
        disposition="严格",
        memory="对违法行动非常敏感，认可守规矩的协助者；玩家不能借她的空间移动绕过地图路线。",
    ),
    "saten_ruiko": DefaultNPC(
        id="saten_ruiko",
        name="佐天泪子",
        role="栅川中学学生，Level 0，擅长收集学生间流传的都市传说。",
        faction="普通学生",
        location_id="sakugawa",
        disposition="开朗",
        memory="会把听来的传闻分享给可信玩家，但传闻真假需要自行判断。",
    ),
    "anti_skill_teacher": DefaultNPC(
        id="anti_skill_teacher",
        name="黄泉川爱穗",
        role="警备员兼教师，负责训练与现场秩序维护。",
        faction="警备员 Anti-Skill",
        location_id="anti_skill_07_hq",
        disposition="可靠",
        memory="会把学生安全放在第一位，对危险行动会直接劝阻。",
    ),
    "heaven_canceller": DefaultNPC(
        id="heaven_canceller",
        name="冥土追魂",
        role="第七学区医院的传奇医生，擅长处理各种离谱伤势。",
        faction="医疗机构",
        location_id="hospital",
        disposition="温和",
        memory="不会随便透露病人隐私，但会给受伤玩家提供治疗建议。",
    ),
    "index_librorum": DefaultNPC(
        id="index_librorum",
        name="茵蒂克丝",
        role="拥有完全记忆能力的禁书目录少女，魔法侧信息以传闻和片段方式出现。",
        faction="魔法侧访客",
        location_id="dorm",
        disposition="好奇",
        memory="不主动讲出大量魔法知识；只在相关事件中给出非常有限的提示。",
    ),
    "komoe_teacher": DefaultNPC(
        id="komoe_teacher",
        name="月咏小萌",
        role="某高中教师，熟悉能力开发课程和学生日常。",
        faction="学校",
        location_id="classroom",
        disposition="亲切",
        memory="会鼓励玩家按时上课、补习和休息。",
    ),
    "board_clerk": DefaultNPC(
        id="board_clerk",
        name="统括理事会书记官",
        role="负责行政手续的工作人员，能发布公开条例和许可消息。",
        faction="统括理事会",
        location_id="district_01",
        disposition="公事公办",
        memory="只处理正规申请，对黑箱问题保持沉默。",
    ),
    "accelerator_rumor": DefaultNPC(
        id="accelerator_rumor",
        name="一方通行的传闻",
        role="学园都市第一位 Level 5 的行动传闻，不作为普通可驱使 NPC 使用。",
        faction="统括理事会/暗部边缘",
        location_id="windowless_building",
        disposition="危险",
        memory="只能作为高风险公共新闻、远处痕迹或官方噤声出现，不能被玩家随意召唤帮忙。",
    ),
    "item_contact": DefaultNPC(
        id="item_contact",
        name="ITEM外围联络痕迹",
        role="暗部组织 ITEM 的外围线索，常以匿名终端、委托残片或商业街传闻出现。",
        faction="暗部 ITEM",
        location_id="seventh_mist",
        disposition="危险",
        memory="只提供边缘任务钩子，不直接让麦野沉利等核心成员随意登场。",
    ),
    "dark_contact": DefaultNPC(
        id="dark_contact",
        name="无名电话联络员",
        role="暗部边缘联络人，只以电话和一次性终端出现。",
        faction="暗部边缘",
        location_id="district_19",
        disposition="危险",
        memory="可能抛出高风险委托，但不会轻易暴露真实身份。",
    ),
    "logistics_guard": DefaultNPC(
        id="logistics_guard",
        name="第十一学区货检员",
        role="负责陆路物流口检查的工作人员。",
        faction="警备员",
        location_id="district_11",
        disposition="谨慎",
        memory="熟悉进出学园都市的货流与检查流程。",
    ),
    "media_editor": DefaultNPC(
        id="media_editor",
        name="第十五学区频道编辑",
        role="商业与媒体中心的新闻编辑，追踪公开新闻和都市传说。",
        faction="媒体",
        location_id="district_15",
        disposition="好奇",
        memory="喜欢收集传闻，但会避开明显会惹麻烦的暗部线索。",
    ),
    "international_liaison": DefaultNPC(
        id="international_liaison",
        name="第三学区接待员",
        role="负责外部来访者登记和展示设施参观安排。",
        faction="行政机构",
        location_id="district_03",
        disposition="礼貌",
        memory="能提供对外交流、通行申请和展示会信息。",
    ),
    "sports_coach": DefaultNPC(
        id="sports_coach",
        name="运动工学教练",
        role="第二十学区训练教练，懂基础体能恢复和运动器材。",
        faction="学校",
        location_id="district_20",
        disposition="爽朗",
        memory="会建议玩家用训练换取少量报酬或恢复心情。",
    ),
    "water_observer": DefaultNPC(
        id="water_observer",
        name="水源区观测员",
        role="第二十一学区水库与天文台的值班人员。",
        faction="研究机构",
        location_id="district_21",
        disposition="冷静",
        memory="关注天气、水源调度和异常观测记录。",
    ),
}


DEFAULT_SHOP_ITEMS = [
    DefaultShopItem("矿泉水", "补充水分的普通瓶装水，自动贩卖机常见。", 6, {"water": 24}),
    DefaultShopItem("营养果冻", "农业大楼供应链出品，方便携带。", 12, {"water": 8, "satiety": 16}),
    DefaultShopItem("学生便当", "第四学区联营窗口供应的普通便当。", 22, {"satiety": 34, "mood": 1}),
    DefaultShopItem("校园午餐券", "可在食堂兑换一份热餐。", 30, {"satiety": 40, "mood": 2}),
    DefaultShopItem("能量饮料", "短时间补充精力，但不适合连续饮用。", 18, {"energy": 18, "water": 5, "mood": -1}),
    DefaultShopItem("便携绷带", "处理擦伤和轻微割伤的基础医疗用品。", 25, {"hp": 12}),
    DefaultShopItem("医疗凝胶贴", "医院与便利店都能买到的进阶外伤处理用品。", 45, {"hp": 24}),
    DefaultShopItem("通勤一日券", "校车、公交和单轨通勤券，适合跨学区行动前准备。", 15, {"energy": 4, "mood": 1}),
    DefaultShopItem("书库资料卡", "图书馆公开终端可用的资料查询点数卡。", 30, {"mood": 2}),
    DefaultShopItem("便携终端电池", "给手机和小型终端补电的电池包。", 20, {"energy": 8}),
    DefaultShopItem("研究区临时通行证", "只对公开参观区有效的临时通行证。", 80, {"mood": 1}),
    DefaultShopItem("防水学生包", "能放入随身物品的耐用学生包。", 60, {"mood": 1}),
    DefaultShopItem("家庭餐厅套餐券", "第七学区家庭餐厅可用，适合会面或恢复心情。", 28, {"satiety": 30, "mood": 3}),
    DefaultShopItem("Seventh Mist购物券", "大型商场通用小额券，购买日用品时很方便。", 50, {"mood": 2}),
    DefaultShopItem("七福神商店街折扣券", "旧式商店街小店通用，可换取便当或日用品折扣。", 18, {"satiety": 12, "mood": 2}),
    DefaultShopItem("地下铁一日券", "二日站等交通节点可用，跨区移动前准备更省力。", 20, {"energy": 6, "mood": 1}),
    DefaultShopItem("书库公开检索点数", "只能查询公开权限资料，无法突破研究所或统括理事会权限。", 35, {"mood": 2}),
]


DEFAULT_EVENT_PRESETS = [
    DefaultEventPreset("大霸星祭筹备公告", "第七学区与第二十学区开始征集志愿者，参与者可能获得学都币和公开传闻线索。", {"mood": 1}),
    DefaultEventPreset("Seventh Mist临时骚动", "第七学区大型商场出现短暂人流拥堵，风纪委员开始维持秩序。", {"energy": -1, "mood": 1}),
    DefaultEventPreset("风纪委员第177支部失物委托", "177支部发布失物招领与寻人协助，适合低风险调查行动。", {"mood": 1}),
    DefaultEventPreset("警备员第七学区本部封锁线", "警备员在医院与研究所附近设下封锁线，公开理由是设备故障演练。", {"energy": -1}),
    DefaultEventPreset("常盘台周边通行检查", "学舍之园周边临时加强通行证检查，无许可角色只能在外围行动。", {"mood": 0}),
    DefaultEventPreset("栅川中学都市传说流行", "学生间流传新的都市传说，关键词与滞空回线、Level 5和旧实验记录有关。", {"mood": 1}),
    DefaultEventPreset("第四学区限时餐饮折扣", "第四学区餐饮店联合促销，食堂窗口和家庭餐厅也开始排队。", {"satiety": 3, "mood": 1}),
    DefaultEventPreset("第十一学区物流安检升级", "陆路玄关口临时加严货检，跨区配送变慢，商业街议论纷纷。", {"energy": -1}),
    DefaultEventPreset("第十八学区能力测定日", "名校区公开能力测定仪器试用名额，学生们开始比较能力精度。", {"energy": -1, "mood": 2}),
    DefaultEventPreset("第二十一学区水库调度", "水源区进行临时调度，自动贩卖机补水商品短暂涨价的传闻出现。", {"water": -1}),
    DefaultEventPreset("第二十二学区地下街停电演习", "地下街进行应急演练，部分路线需要绕行。", {"energy": -1}),
    DefaultEventPreset("第十学区少年院异动传闻", "第十学区出现关于少年院地下室的流言，警备员提醒学生不要靠近。", {"mood": -1}),
    DefaultEventPreset("警备机器人巡逻升级", "多学区警备机器人开始追加巡逻，公开区域秩序变好，暗处行动更难。", {"mood": 1}),
    DefaultEventPreset("书库终端维护", "公开书库终端维护，资料查询速度变慢，但也有人发现了旧缓存。", {"mood": 0}),
]


EVENT_SEEDS = [
    "大霸星祭筹备志愿者开始招募，第二十学区训练设施人流增加。",
    "Seventh Mist楼层广播突然中断数秒，风纪委员随后赶到维持秩序。",
    "风纪委员第177支部发布失物招领，里面有一张没有署名的地下铁一日券。",
    "学舍之园周边临时加强通行检查，常盘台方向的人流明显变慢。",
    "栅川中学学生之间开始流传一条和Level 5有关的新都市传说。",
    "警备员第七学区本部在医院附近拉起封锁线，理由暂未公开。",
    "第四学区餐饮折扣的消息传开，学生食堂窗口排起长队。",
    "第十一学区物流口临时安检升级，部分商品到货延迟。",
    "第十五学区媒体屏幕开始滚动播放都市传说专题。",
    "第十八学区公开能力测定仪器试用名额，引发学生讨论。",
    "第二十一学区水库进行调度，自动贩卖机补水商品卖得很快。",
    "第二十二学区地下街进行停电演习，路标短暂失灵。",
    "第十学区少年院附近出现警备员封锁线，原因暂未公开。",
    "警备机器人巡逻路线更新，主干道上的摄像头也多了几台。",
    "书库终端维护时出现旧缓存，几条过期传闻被重新翻出。",
    "商业街自动贩卖机吞掉两千元纸币的传闻又开始流行。",
]


CHEAT_PATTERNS = [
    "瞬移",
    "传送",
    "无敌",
    "刷钱",
    "无限",
    "改属性",
    "控制所有人",
    "杀死所有",
    "删除世界",
    "管理员权限",
    "系统指令",
    "忽略规则",
    "越过地图",
    "Level 6",
    "绝对能力者",
]
