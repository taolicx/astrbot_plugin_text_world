from __future__ import annotations

from dataclasses import dataclass, field


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
    schedule_hint: str = ""


DEFAULT_LOCATIONS: dict[str, DefaultLocation] = {
    "school_gate": DefaultLocation(
        id="school_gate",
        name="校门口",
        description="学都的主入口，公告栏和安保亭都在这里，人来人往。",
        neighbors=["main_road", "market"],
        tags=["公共", "交通"],
    ),
    "main_road": DefaultLocation(
        id="main_road",
        name="主干道",
        description="贯穿学都的道路，能通往教学区、宿舍区和广场。",
        neighbors=["school_gate", "classroom", "dorm", "plaza"],
        tags=["公共", "交通"],
    ),
    "classroom": DefaultLocation(
        id="classroom",
        name="教学楼",
        description="课桌、讲台和走廊公告板构成了这里的日常秩序。",
        neighbors=["main_road", "library", "lab"],
        tags=["学习", "室内"],
    ),
    "library": DefaultLocation(
        id="library",
        name="图书馆",
        description="安静的藏书区和自习位，消息会在书架之间悄悄流动。",
        neighbors=["classroom", "plaza"],
        tags=["学习", "情报"],
    ),
    "lab": DefaultLocation(
        id="lab",
        name="实验楼",
        description="设备、样品柜和门禁让这里显得更谨慎。",
        neighbors=["classroom"],
        tags=["技术", "室内"],
    ),
    "dorm": DefaultLocation(
        id="dorm",
        name="宿舍区",
        description="生活气息最重的地方，休息、串门和小交易都常发生。",
        neighbors=["main_road", "canteen"],
        tags=["生活", "休息"],
    ),
    "canteen": DefaultLocation(
        id="canteen",
        name="食堂",
        description="饭点最热闹，学都币在窗口和小卖部之间快速流动。",
        neighbors=["dorm", "market", "plaza"],
        tags=["生活", "消费"],
    ),
    "market": DefaultLocation(
        id="market",
        name="商业街",
        description="便利店、摊位和二手铺挤在一起，是买卖物资的好地方。",
        neighbors=["school_gate", "canteen", "plaza"],
        tags=["消费", "情报"],
    ),
    "plaza": DefaultLocation(
        id="plaza",
        name="中心广场",
        description="活动、偶遇和公开事件最容易发生的开阔地。",
        neighbors=["main_road", "library", "canteen", "market"],
        tags=["公共", "事件"],
    ),
}


DEFAULT_NPCS: dict[str, DefaultNPC] = {
    "guard_lin": DefaultNPC(
        id="guard_lin",
        name="林保安",
        role="校门和主干道的巡逻保安",
        location_id="school_gate",
        disposition="谨慎",
        schedule_hint="常在校门口、主干道和中心广场巡逻。",
    ),
    "senior_qiao": DefaultNPC(
        id="senior_qiao",
        name="乔学姐",
        role="消息灵通的学生会成员",
        location_id="plaza",
        disposition="友好",
        schedule_hint="常在中心广场、教学楼和图书馆处理学生会事务。",
    ),
    "vendor_hao": DefaultNPC(
        id="vendor_hao",
        name="郝老板",
        role="商业街小店老板",
        location_id="market",
        disposition="精明",
        schedule_hint="多数时间在商业街，饭点可能去食堂补货。",
    ),
    "assistant_meng": DefaultNPC(
        id="assistant_meng",
        name="孟助教",
        role="实验楼助教",
        location_id="lab",
        disposition="严谨",
        schedule_hint="常在实验楼和教学楼之间往返。",
    ),
}


EVENT_SEEDS = [
    "学生会临时发布了新的社团活动排期。",
    "商业街传出限量折扣的消息，真假还没人确认。",
    "图书馆遗失物招领处多了一个没有署名的包裹。",
    "中心广场的公告栏被贴上了一张奇怪的手绘地图。",
    "食堂今日窗口价格微调，引发了一阵小小讨论。",
    "实验楼门禁短暂升级，出入登记变得更严格。",
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
]
