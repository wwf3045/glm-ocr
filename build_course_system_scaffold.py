from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil


LIB_ROOT = Path(r"F:\资料库")
MID_ROOT = Path(r"F:\中间文件库")
KB_ROOT = Path(r"F:\Obsidian\Obsidian env\Knowledge World")
REPORT_ROOT = Path(r"C:\Users\28033\Desktop\GLM-OCR\audit_reports")
REPORT_PATH = REPORT_ROOT / "20260314_course_system_setup.md"
JSON_REPORT_PATH = REPORT_ROOT / "20260314_course_system_setup.json"

LIB_SUBDIRS = ["教材及参考书", "课件", "课程资料", "作业与复习", "实验与项目"]
MID_SUBDIRS = ["教材OCR扫描", "课件OCR扫描", "课程资料OCR扫描"]
EXCLUDED_KB_CATEGORIES = {"Calibre书库", "大学英语", "高中", "其他"}
EXCLUDED_MID_CATEGORIES = {"Calibre书库", "大学英语", "高中", "其他"}


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    include_in_kb: bool = True


@dataclass(frozen=True)
class Subject:
    name: str
    category: str
    kb_name: str | None = None
    kb_include: bool = True
    library_sources: tuple[tuple[str, str], ...] = ()
    middle_sources: tuple[tuple[str, str], ...] = ()
    library_refs: tuple[str, ...] = ()
    middle_refs: tuple[str, ...] = ()
    placeholder_library: bool = False
    placeholder_middle: bool = False
    scaffold_library_subdirs: bool = True
    scaffold_middle_subdirs: bool = True
    note: str = ""
    subitems: tuple[str, ...] = ()


CATEGORIES = [
    Category("考研", "考研资料总类。知识体系里当前只纳入初试主线。"),
    Category("政治", "思想政治类公共课与非考研政治课程。"),
    Category("数学", "按分析、代数、几何与拓扑、概率与统计、规划与优化、离散数学组织。"),
    Category("物理", "大学物理与相关基础课程。"),
    Category("计算机科学与技术", "非考研初试的计算机专业课。"),
    Category("编程开发", "编程语言、开发工具与工程实践。"),
    Category("人工智能", "AI 主干与方向课。"),
    Category("集成电路", "芯片与硬件方向资料。"),
    Category("电气工程与自动化", "电路与信号相关课程。"),
    Category("通信工程", "通信与信息系统方向课程。"),
    Category("Calibre书库", "电子书总库，默认不进入知识体系。", include_in_kb=False),
    Category("大学英语", "英语课程资料存档，默认不进入知识体系。", include_in_kb=False),
    Category("高中", "高中历史资料存档，默认不进入知识体系。", include_in_kb=False),
    Category("其他", "杂项与非课程资料存档，默认不进入知识体系。", include_in_kb=False),
]

PHYSICAL_DESKTOP_RETAIN = [
    "考研",
    "政治",
    "数学",
    "物理",
    "计算机科学与技术",
    "编程开发",
    "人工智能",
    "集成电路",
    "电气工程与自动化",
    "通信工程",
    "Calibre书库",
    "大学英语",
    "高中",
    "其他\\学校",
    "其他\\说明书",
    "其他\\作文",
    "其他\\杂项",
    "其他\\WeChat Files（过去）",
]

EXAM_ALIAS_MERGES = [
    ("考研\\计算机专业课\\C++程序设计", "考研\\计算机专业课\\程序设计基础（C++）"),
    ("考研\\计算机专业课\\Algorithm", "考研\\计算机专业课\\算法设计与分析"),
    ("考研\\计算机专业课\\数据结构（C++）", "考研\\计算机专业课\\数据结构"),
    ("考研\\考研数学\\数学分析", "考研\\考研数学\\高等数学"),
    ("考研\\考研数学\\三大计算", "考研\\考研数学\\高等数学"),
    ("考研\\考研数学\\离散数学", "数学\\离散数学"),
    ("考研\\考研数学\\高等代数", "数学\\代数\\高等代数"),
    ("数学\\分析\\傅里叶分析（入门）", "数学\\分析\\傅里叶分析"),
]

SUBJECT_SUBITEM_ALIASES: dict[tuple[str, str], dict[str, str]] = {
    ("数学", "分析"): {
        "高等数学": "高等数学",
        "数学分析": "数学分析",
        "实变函数": "实变函数",
        "复分析": "复分析",
        "泛函分析": "泛函分析",
        "测度论": "测度论",
        "傅里叶分析（入门）": "傅里叶分析",
        "傅里叶分析": "傅里叶分析",
        "渐进分析": "渐进分析",
        "常微分方程": "常微分方程",
        "偏微分方程（数学物理方法）": "偏微分方程（数学物理方法）",
    },
    ("数学", "代数"): {
        "线性代数": "线性代数",
        "高等代数": "高等代数",
        "矩阵理论": "矩阵理论",
        "抽象代数": "抽象代数（近世代数）",
        "近世代数": "抽象代数（近世代数）",
        "抽象代数（近世代数）": "抽象代数（近世代数）",
        "初等数论": "初等数论",
    },
    ("数学", "概率与统计"): {
        "概率论与数理统计": "概率论与数理统计",
        "随机过程": "随机过程",
        "高等概率论": "高等概率论",
    },
    ("数学", "规划与优化"): {
        "最优化": "最优化理论",
        "最优化理论": "最优化理论",
        "线性优化与凸优化": "最优化理论",
        "数值优化": "数值优化",
        "数值分析": "数值分析",
        "误差理论": "误差理论",
    },
    ("数学", "离散数学"): {
        "数理逻辑": "数理逻辑",
        "集合论": "集合论",
        "图论": "图论",
        "组合数学": "组合数学",
    },
}

LIB_BUCKET_ALIASES = {
    "教材": "教材及参考书",
    "参考书": "教材及参考书",
    "教材与参考书": "教材及参考书",
}

SUBJECTS = [
    Subject(
        name="考研数学",
        category="考研",
        library_sources=(("考研数学", "考研数学"), ("考研数学一", "考研数学")),
        middle_sources=(("考研数学", "考研数学"), ("考研数学一", "考研数学")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="考研初试数学主线。知识体系统一按具体学科组织，不再按数一/数二单独建树；当前目标院校口径对应数学一。",
        subitems=("高等数学", "线性代数", "概率论与数理统计", "张宇基础30讲", "张宇强化36讲"),
    ),
    Subject(
        name="考研英语",
        category="考研",
        library_sources=(("考研英语", "考研英语"), ("考研英语一", "考研英语")),
        middle_sources=(("考研英语", "考研英语"), ("考研英语一", "考研英语")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="考研初试英语主线。知识体系统一按具体题型与能力模块组织，不再按英一/英二单独建树；当前目标院校口径对应英语一。",
        subitems=("词汇", "语法与长难句", "阅读", "新题型", "翻译", "写作"),
    ),
    Subject(
        name="考研政治",
        category="考研",
        library_sources=(("考研政治", "考研政治"),),
        middle_sources=(("考研政治", "考研政治"),),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="考研初试政治主线。",
        subitems=("马克思主义基本原理", "毛泽东思想和中国特色社会主义理论体系概论", "中国近现代史纲要", "思想道德与法治", "时政"),
    ),
    Subject(
        name="计算机专业课",
        category="考研",
        library_sources=(("计算机专业课", "计算机专业课"), ("408-826", "计算机专业课"), ("考研408", "计算机专业课")),
        middle_sources=(("计算机专业课", "计算机专业课"), ("408-826", "计算机专业课"), ("考研408", "计算机专业课")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="考研计算机专业课主线。知识体系统一按具体课程组织；408 对应数据结构、计算机组成原理、操作系统、计算机网络，当前备考口径额外补入 C++ 与算法，826 只作为目标院校映射标签保留。",
        subitems=("程序设计基础（C++）", "数据结构", "算法设计与分析", "操作系统", "计算机网络", "计算机组成原理"),
    ),
    Subject(
        name="考研总资料",
        category="考研",
        kb_include=False,
        library_refs=("考研",),
        note="既有综合考研资料归档入口，不进入知识体系主结构。",
    ),
    Subject(
        name="马克思主义基本原理",
        category="政治",
        library_sources=(("政治\\马克思主义基本原理", "马克思主义基本原理"), ("考研\\考研政治\\马克思主义基本原理", "马克思主义基本原理")),
        middle_sources=(("政治\\马克思主义基本原理", "马克思主义基本原理"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="公共政治课课程位，和考研政治中的同名模块分开管理。",
    ),
    Subject(
        name="毛泽东思想和中国特色社会主义理论体系概论",
        category="政治",
        library_sources=(("政治\\毛泽东思想和中国特色社会主义理论体系概论", "毛泽东思想和中国特色社会主义理论体系概论"), ("考研\\考研政治\\毛泽东思想和中国特色社会主义理论体系概论", "毛泽东思想和中国特色社会主义理论体系概论"), ("考研\\考研政治\\毛中特", "毛泽东思想和中国特色社会主义理论体系概论")),
        middle_sources=(("政治\\毛泽东思想和中国特色社会主义理论体系概论", "毛泽东思想和中国特色社会主义理论体系概论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="公共政治课课程位，统一采用完整课程名。",
    ),
    Subject(
        name="中国近现代史纲要",
        category="政治",
        library_sources=(("政治\\中国近现代史纲要", "中国近现代史纲要"), ("考研\\考研政治\\中国近现代史纲要", "中国近现代史纲要")),
        middle_sources=(("政治\\中国近现代史纲要", "中国近现代史纲要"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="公共政治课课程位。",
    ),
    Subject(
        name="思想道德与法治",
        category="政治",
        library_sources=(("政治\\思想道德与法治", "思想道德与法治"), ("考研\\考研政治\\思想道德与法治", "思想道德与法治"), ("考研\\考研政治\\思想道德修养与法律基础", "思想道德与法治")),
        middle_sources=(("政治\\思想道德与法治", "思想道德与法治"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="公共政治课课程位，统一采用新版课程名。",
    ),
    Subject(
        name="习近平新时代中国特色社会主义思想概论",
        category="政治",
        library_sources=(("政治\\习近平新时代中国特色社会主义思想概论", "习近平新时代中国特色社会主义思想概论"), ("考研\\考研政治\\习近平新时代中国特色社会主义思想概论", "习近平新时代中国特色社会主义思想概论")),
        middle_sources=(("政治\\习近平新时代中国特色社会主义思想概论", "习近平新时代中国特色社会主义思想概论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="公共政治课课程位。",
    ),
    Subject(
        name="军事理论",
        category="政治",
        library_sources=(("政治\\军事理论", "军事理论"), ("考研\\考研政治\\军事理论", "军事理论")),
        middle_sources=(("政治\\军事理论", "军事理论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="学校公共课程位，单独从考研政治中拆出。",
    ),
    Subject(
        name="分析",
        category="数学",
        library_sources=(("数学1 分析", "分析"), ("数学基础\\高等数学", "分析\\高等数学")),
        middle_sources=(("数学基础\\高等数学", "分析\\高等数学"),),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="对应实体桌面的“分析”大类，当前重点材料包括高等数学。",
        subitems=("高等数学", "数学分析", "实变函数", "复分析", "泛函分析", "测度论", "傅里叶分析", "渐进分析", "常微分方程", "偏微分方程（数学物理方法）"),
    ),
    Subject(
        name="代数",
        category="数学",
        library_sources=(("代数与方程", "代数"), ("数学2 代数与方程", "代数"), ("数学基础\\线性代数", "代数\\线性代数")),
        middle_sources=(("代数与方程", "代数"), ("数学基础\\线性代数", "代数\\线性代数")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="对应实体桌面的“代数”大类，当前重点材料包括线性代数、高等代数，以及更进阶的代数方向内容。",
        subitems=("线性代数", "高等代数", "矩阵理论", "抽象代数（近世代数）", "初等数论"),
    ),
    Subject(
        name="几何与拓扑",
        category="数学",
        library_sources=(("数学3 几何与拓扑", "几何与拓扑"),),
        middle_sources=(("几何与拓扑", "几何与拓扑"),),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="对应实体桌面的“几何与拓扑”大类。",
        subitems=("空间解析几何", "点集拓扑"),
    ),
    Subject(
        name="概率与统计",
        category="数学",
        library_sources=(("数学4 概率与统计", "概率与统计"), ("数学基础\\概率论与数理统计", "概率与统计\\概率论与数理统计"), ("随机过程", "概率与统计\\随机过程")),
        middle_sources=(("数学基础\\概率论与数理统计", "概率与统计\\概率论与数理统计"), ("随机过程", "概率与统计\\随机过程")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="对应实体桌面的“概率与统计”大类，当前重点材料包括概率论与数理统计、随机过程。",
        subitems=("概率论与数理统计", "高等概率论", "随机过程"),
    ),
    Subject(
        name="规划与优化",
        category="数学",
        library_sources=(("数学6 规划与优化", "规划与优化"), ("最优化", "规划与优化\\最优化理论"), ("最优化理论", "规划与优化\\最优化理论"), ("线性优化与凸优化", "规划与优化\\最优化理论")),
        middle_sources=(("最优化", "规划与优化\\最优化理论"), ("最优化理论", "规划与优化\\最优化理论"), ("线性优化与凸优化", "规划与优化\\最优化理论")),
        placeholder_library=True,
        placeholder_middle=True,
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="对应实体桌面的“规划与优化”大类，当前已统一收拢到“最优化理论”及其周边方向。",
        subitems=("最优化理论", "数值优化", "数值分析", "误差理论"),
    ),
    Subject(
        name="离散数学",
        category="数学",
        library_sources=(("离散数学", "离散数学"), ("数理逻辑", "离散数学\\数理逻辑")),
        middle_sources=(("离散数学", "离散数学"), ("数理逻辑", "离散数学\\数理逻辑")),
        scaffold_library_subdirs=False,
        scaffold_middle_subdirs=False,
        note="数学中的独立大类，内部按数理逻辑、集合论、图论组织。",
        subitems=("数理逻辑", "集合论", "图论", "组合数学"),
    ),
    Subject(
        name="程序设计基础（C++）",
        category="考研",
        library_sources=(("计算机科学与技术\\程序设计基础（C++）", "计算机专业课\\程序设计基础（C++）"), ("计算机科学与技术\\程序设计思想与方法（C++）", "计算机专业课\\程序设计基础（C++）")),
        middle_sources=(("计算机科学与技术\\程序设计基础（C++）", "计算机专业课\\程序设计基础（C++）"), ("计算机科学与技术\\程序设计思想与方法（C++）", "计算机专业课\\程序设计基础（C++）")),
        library_refs=("考研\\计算机专业课\\程序设计基础（C++）", "考研\\计算机专业课\\程序设计思想与方法（C++）"),
        middle_refs=("考研\\计算机专业课\\程序设计基础（C++）", "考研\\计算机专业课\\程序设计思想与方法（C++）"),
        placeholder_library=True,
        placeholder_middle=True,
        note="考研计算机专业课主线中的 C++ 编程入口，统一采用更通用的课程名。",
    ),
    Subject(
        name="数据结构",
        category="考研",
        library_sources=(("计算机科学与技术\\数据结构", "计算机专业课\\数据结构"),),
        middle_sources=(("计算机科学与技术\\数据结构", "计算机专业课\\数据结构"),),
        library_refs=("考研\\计算机专业课\\数据结构",),
        middle_refs=("考研\\计算机专业课\\数据结构",),
        note="考研计算机专业课主线中的核心课程，已完成 101 计划乱码课件重命名与 OCR 归并。",
    ),
    Subject(
        name="算法设计与分析",
        category="考研",
        library_sources=(("计算机科学与技术\\算法设计与分析", "计算机专业课\\算法设计与分析"),),
        middle_sources=(("计算机科学与技术\\算法设计与分析", "计算机专业课\\算法设计与分析"),),
        library_refs=("考研\\计算机专业课\\算法设计与分析",),
        middle_refs=("考研\\计算机专业课\\算法设计与分析",),
        placeholder_library=True,
        placeholder_middle=True,
        note="考研计算机专业课主线中的算法入口。",
    ),
    Subject(
        name="操作系统",
        category="考研",
        library_sources=(("计算机科学与技术\\操作系统", "计算机专业课\\操作系统"),),
        middle_sources=(("计算机科学与技术\\操作系统", "计算机专业课\\操作系统"),),
        library_refs=("考研\\计算机专业课\\操作系统",),
        middle_refs=("考研\\计算机专业课\\操作系统",),
        note="考研计算机专业课主线中的操作系统入口，原件库与 OCR 中间库已整理完成。",
    ),
    Subject(
        name="计算机组成原理",
        category="考研",
        library_refs=("考研\\计算机专业课\\计算机组成原理",),
        middle_refs=("考研\\计算机专业课\\计算机组成原理",),
        note="考研计算机专业课主线中的组成原理入口，对应 408 / 826 中的硬件基础模块。",
    ),
    Subject(
        name="计算机网络",
        category="考研",
        library_sources=(("计算机科学与技术\\计算机网络", "计算机专业课\\计算机网络"),),
        middle_sources=(("计算机科学与技术\\计算机网络", "计算机专业课\\计算机网络"),),
        library_refs=("考研\\计算机专业课\\计算机网络",),
        middle_refs=("考研\\计算机专业课\\计算机网络",),
        note="考研计算机专业课主线中的计算机网络入口，课程资料与既有考研资料统一收拢到同一目录。",
    ),
    Subject(
        name="计算机体系结构",
        category="计算机科学与技术",
        library_sources=(("考研\\计算机专业课\\计算机体系结构", "计算机体系结构"),),
        middle_sources=(("考研\\计算机专业课\\计算机体系结构", "计算机体系结构"),),
        library_refs=("计算机科学与技术\\计算机体系结构",),
        middle_refs=("计算机科学与技术\\计算机体系结构",),
        note="作为独立课程保留在计算机科学与技术主类下，不再放入考研初试主结构。",
        subitems=("计算机组成与实现", "计算机系统"),
    ),
    Subject(
        name="数据库原理",
        category="计算机科学与技术",
        library_sources=(("数据库管理系统", "数据库原理"),),
        middle_sources=(("数据库管理系统", "数据库原理"),),
        note="知识体系统一采用国内更常见的课程名“数据库原理”，原始来源目录来自此前的“数据库管理系统”。",
    ),
    Subject(
        name="编译原理",
        category="计算机科学与技术",
        library_sources=(("编译原理", "编译原理"),),
        middle_sources=(("编译原理", "编译原理"),),
        note="原件库和中间文件库均已归并。",
    ),
    Subject(
        name="软件工程",
        category="计算机科学与技术",
        library_sources=(("软件工程", "软件工程"),),
        middle_sources=(("软件工程", "软件工程"),),
        note="已有原件库和中间文件库。",
    ),
    Subject(
        name="计算机科学导论",
        category="计算机科学与技术",
        library_sources=(("计算机科学导论", "计算机科学导论"),),
        middle_sources=(("计算机科学导论", "计算机科学导论"),),
        note="已有原件库和中间文件库。",
    ),
    Subject(
        name="分布式系统",
        category="计算机科学与技术",
        library_sources=(("分布式系统", "分布式系统"),),
        middle_sources=(("分布式系统", "分布式系统"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入的非考研课，偏大模型训练、推理服务与大规模计算系统。",
    ),
    Subject(
        name="并行计算",
        category="计算机科学与技术",
        library_sources=(("并行计算", "并行计算"),),
        middle_sources=(("并行计算", "并行计算"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入的非考研课，用于承接 GPU、CUDA 与高性能计算相关资料。",
    ),
    Subject(
        name="计算机图形学",
        category="计算机科学与技术",
        library_sources=(("计算机图形学", "计算机图形学"),),
        middle_sources=(("计算机图形学", "计算机图形学"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="和三维视觉、渲染、仿真相关的计算机基础课，按研究方向补入。",
    ),
    Subject(
        name="高性能计算",
        category="计算机科学与技术",
        library_sources=(("高性能计算", "高性能计算"),),
        middle_sources=(("高性能计算", "高性能计算"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="承接高性能科学与工程计算相关教材与后续并行计算资料的独立课程位。",
    ),
    Subject(
        name="计算理论",
        category="计算机科学与技术",
        library_sources=(("计算理论", "计算理论"),),
        middle_sources=(("计算理论", "计算理论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="承接自动机理论、形式语言与可计算性相关教材的独立课程位。",
    ),
    Subject(
        name="Python",
        category="编程开发",
        library_sources=(("Python", "Python"),),
        middle_sources=(("Python", "Python"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="编程开发主类中的 Python 入口。",
    ),
    Subject(
        name="Java",
        category="编程开发",
        library_sources=(("Java", "Java"),),
        middle_sources=(("Java", "Java"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="编程开发主类中的 Java 入口。",
    ),
    Subject(
        name="Git与Linux",
        category="编程开发",
        library_sources=(("Git与Linux", "Git与Linux"),),
        middle_sources=(("Git与Linux", "Git与Linux"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="命令行、版本控制与开发环境工具入口。",
    ),
    Subject(
        name="Docker",
        category="编程开发",
        library_sources=(("Docker", "Docker"),),
        middle_sources=(("Docker", "Docker"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="容器与部署相关开发资料入口。",
    ),
    Subject(
        name="Web开发",
        category="编程开发",
        library_sources=(("Web开发", "Web开发"),),
        middle_sources=(("Web开发", "Web开发"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="前后端与 Web 应用开发入口。",
    ),
    Subject(
        name="PyTorch",
        category="编程开发",
        library_sources=(("PyTorch", "PyTorch"),),
        middle_sources=(("PyTorch", "PyTorch"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="面向深度学习与基础模型实验的主力框架入口。",
    ),
    Subject(
        name="CUDA与并行计算",
        category="编程开发",
        library_sources=(("CUDA与并行计算", "CUDA与并行计算"),),
        middle_sources=(("CUDA与并行计算", "CUDA与并行计算"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="面向 GPU 编程、性能优化与大模型训练基础设施的开发入口。",
    ),
    Subject(
        name="实验工程与MLOps",
        category="编程开发",
        library_sources=(("实验工程与MLOps", "实验工程与MLOps"),),
        middle_sources=(("实验工程与MLOps", "实验工程与MLOps"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="面向实验管理、训练流程、部署和可复现工程化的入口。",
    ),
    Subject(
        name="人工智能基础",
        category="人工智能",
        kb_include=False,
        library_sources=(("人工智能基础", "人工智能基础"),),
        middle_sources=(("人工智能基础", "人工智能基础"),),
        note="资料层保留，但不进入知识体系主结构。",
    ),
    Subject(
        name="机器学习",
        category="人工智能",
        library_sources=(("机器学习", "机器学习"),),
        note="当前以原件层为主，中间库后续补齐。",
    ),
    Subject(
        name="深度学习",
        category="人工智能",
        library_sources=(("深度学习", "深度学习"),),
        middle_sources=(("深度学习", "深度学习"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="AI 主干课，占位建立，后续承接课程与网课资源。",
    ),
    Subject(
        name="计算机视觉",
        category="人工智能",
        library_sources=(("计算机视觉", "计算机视觉"),),
        middle_sources=(("计算机视觉", "计算机视觉"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="AI 主干课，占位建立，后续承接视觉与多模态相关资料。",
    ),
    Subject(
        name="数据挖掘",
        category="人工智能",
        library_sources=(("数据挖掘", "数据挖掘"),),
        note="当前以原件层为主，中间库后续补齐。",
    ),
    Subject(
        name="自然语言处理",
        category="人工智能",
        library_sources=(("自然语言处理", "自然语言处理"),),
        note="当前以原件层为主，中间库后续补齐。",
    ),
    Subject(
        name="强化学习",
        category="人工智能",
        library_sources=(("强化学习", "强化学习"),),
        middle_sources=(("强化学习", "强化学习"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="秋季重点课，先建立课程位。",
    ),
    Subject(
        name="大模型技术",
        category="人工智能",
        library_sources=(("大模型技术", "大模型技术"),),
        middle_sources=(("大模型技术", "大模型技术"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="热门方向课，先建立课程位。",
    ),
    Subject(
        name="生成模型",
        category="人工智能",
        library_sources=(("生成模型", "生成模型"),),
        middle_sources=(("生成模型", "生成模型"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入，用于承接扩散模型、生成式建模与基础模型训练相关资料。",
    ),
    Subject(
        name="多模态智能",
        category="人工智能",
        library_sources=(("多模态智能", "多模态智能"),),
        middle_sources=(("多模态智能", "多模态智能"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="保留为研究方向节点，但默认聚焦真正能提升视觉理解与闭环能力的多模态路线。",
    ),
    Subject(
        name="三维视觉与视频理解",
        category="人工智能",
        library_sources=(("三维视觉与视频理解", "三维视觉与视频理解"),),
        middle_sources=(("三维视觉与视频理解", "三维视觉与视频理解"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="对应你更看重的视觉基础能力、视频理解、时空建模与三维感知方向。",
    ),
    Subject(
        name="世界模型",
        category="人工智能",
        library_sources=(("世界模型", "世界模型"),),
        middle_sources=(("世界模型", "世界模型"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入，作为感知、预测、规划和具身智能闭环的核心节点。",
    ),
    Subject(
        name="具身智能",
        category="人工智能",
        library_sources=(("具身智能", "具身智能"),),
        middle_sources=(("具身智能", "具身智能"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="当前最看好的主线之一，但只接受偏感知、决策、世界模型和基础模型驱动的路线。",
    ),
    Subject(
        name="机器人感知与决策",
        category="人工智能",
        library_sources=(("机器人感知与决策", "机器人感知与决策"),),
        middle_sources=(("机器人感知与决策", "机器人感知与决策"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入，用于承接机器人感知、规划、策略学习和决策闭环相关资料。",
    ),
    Subject(
        name="AI for Science",
        category="人工智能",
        library_sources=(("AI for Science", "AI for Science"),),
        middle_sources=(("AI for Science", "AI for Science"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="方向 D 课程，先建立课程位。",
    ),
    Subject(
        name="虚拟现实",
        category="人工智能",
        library_sources=(("虚拟现实", "虚拟现实"),),
        middle_sources=(("虚拟现实", "虚拟现实"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="方向 D 课程，先建立课程位。",
    ),
    Subject(
        name="模拟电子技术",
        category="集成电路",
        library_sources=(("模拟电子技术", "模拟电子技术"),),
        middle_sources=(("模拟电子技术", "模拟电子技术"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="微电子方向基础课程，占位建立。",
    ),
    Subject(
        name="数字电子技术",
        category="集成电路",
        library_sources=(("数字电子技术", "数字电子技术"),),
        middle_sources=(("数字电子技术", "数字电子技术"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="微电子方向基础课程，占位建立。",
    ),
    Subject(
        name="半导体物理",
        category="集成电路",
        library_sources=(("半导体物理", "半导体物理"),),
        middle_sources=(("半导体物理", "半导体物理"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="微电子方向课程，占位建立。",
    ),
    Subject(
        name="固体物理",
        category="集成电路",
        library_sources=(("固体物理", "固体物理"),),
        middle_sources=(("固体物理", "固体物理"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="与半导体物理分开的独立课程，承接固体物理相关教材与后续资料。",
    ),
    Subject(
        name="半导体器件",
        category="集成电路",
        library_sources=(("半导体器件", "半导体器件"),),
        middle_sources=(("半导体器件", "半导体器件"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="微电子方向课程，占位建立。",
    ),
    Subject(
        name="半导体工艺",
        category="集成电路",
        library_sources=(("半导体工艺", "半导体工艺"),),
        middle_sources=(("半导体工艺", "半导体工艺"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="微电子方向课程，占位建立。",
    ),
    Subject(
        name="信号与系统",
        category="电气工程与自动化",
        library_sources=(("信号与系统", "信号与系统"),),
        middle_sources=(("信号与系统", "信号与系统"),),
        note="冲突参考书已完成替换，并通过 GLM-OCR 核验。",
    ),
    Subject(
        name="大学物理1",
        category="物理",
        library_sources=(("大学物理1", "大学物理1"),),
        middle_sources=(("大学物理1", "大学物理1"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="物理大类下的基础课程位，先建立占位。",
    ),
    Subject(
        name="大学物理2",
        category="物理",
        library_sources=(("大学物理2", "大学物理2"),),
        note="当前原件库已有，中间库后续补齐。",
    ),
    Subject(
        name="大学物理3",
        category="物理",
        library_sources=(("大学物理3", "大学物理3"),),
        middle_sources=(("大学物理3", "大学物理3"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="资料可能仍在 E 盘，先建立占位。",
    ),
    Subject(
        name="电路理论",
        category="电气工程与自动化",
        library_sources=(("电路理论", "电路理论"),),
        middle_sources=(("电路理论", "电路理论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="资料暂未完全迁入，先建立占位。",
    ),
    Subject(
        name="电机学",
        category="电气工程与自动化",
        library_sources=(("电机学", "电机学"),),
        middle_sources=(("电机学", "电机学"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="电气工程与自动化方向基础课程，占位建立。",
    ),
    Subject(
        name="自动控制原理",
        category="电气工程与自动化",
        library_sources=(("自动控制原理", "自动控制原理"),),
        middle_sources=(("自动控制原理", "自动控制原理"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="电气工程与自动化方向基础课程，占位建立。",
    ),
    Subject(
        name="现代控制理论",
        category="电气工程与自动化",
        library_sources=(("现代控制理论", "现代控制理论"),),
        middle_sources=(("现代控制理论", "现代控制理论"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="电气工程与自动化方向课程，占位建立。",
    ),
    Subject(
        name="机器人运动学",
        category="电气工程与自动化",
        library_sources=(("机器人运动学", "机器人运动学"),),
        middle_sources=(("机器人运动学", "机器人运动学"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="按研究方向补入，作为具身智能相关但偏基础的机器人课程入口。",
    ),
    Subject(
        name="状态估计与传感器融合",
        category="电气工程与自动化",
        library_sources=(("状态估计与传感器融合", "状态估计与传感器融合"),),
        middle_sources=(("状态估计与传感器融合", "状态估计与传感器融合"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="面向机器人感知、定位与闭环系统的基础课程入口，按研究方向补入。",
    ),
    Subject(
        name="通信原理",
        category="通信工程",
        library_sources=(("通信原理", "通信原理"),),
        middle_sources=(("通信原理", "通信原理"),),
        placeholder_library=True,
        placeholder_middle=True,
        note="通信工程方向基础课程，占位建立。",
    ),
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def safe_name(name: str) -> str:
    return name.replace("/", "-")


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def cleanup_previous_generated_notes() -> None:
    old_files = ["01-公共基础课.md", "02-必修课.md", "03-专业选修课.md"]
    for filename in old_files:
        path = KB_ROOT / filename
        if path.exists():
            path.unlink()
    old_dir = KB_ROOT / "课程卡片"
    if old_dir.exists():
        shutil.rmtree(old_dir)
    stale_notes = [
        KB_ROOT / "数学" / "数理逻辑入门.md",
        KB_ROOT / "数学" / "数理逻辑.md",
        KB_ROOT / "数学" / "数学基础（数分-线代-概统）.md",
        KB_ROOT / "数学" / "数学基础.md",
        KB_ROOT / "数学" / "代数与方程.md",
        KB_ROOT / "数学" / "线性优化与凸优化.md",
        KB_ROOT / "数学" / "最优化.md",
        KB_ROOT / "数学" / "随机过程.md",
        KB_ROOT / "考研" / "考研数学一.md",
        KB_ROOT / "考研" / "考研英语一.md",
        KB_ROOT / "考研" / "408-826.md",
        KB_ROOT / "考研" / "计算机体系结构.md",
        KB_ROOT / "计算机科学与技术" / "计算机科学与技术（综合）.md",
        KB_ROOT / "计算机科学与技术" / "程序设计基础（C++）.md",
        KB_ROOT / "计算机科学与技术" / "数据结构.md",
        KB_ROOT / "计算机科学与技术" / "算法设计与分析.md",
        KB_ROOT / "计算机科学与技术" / "操作系统.md",
        KB_ROOT / "计算机科学与技术" / "计算机网络.md",
        KB_ROOT / "计算机科学与技术" / "数据库管理系统.md",
        KB_ROOT / "人工智能" / "人工智能（综合）.md",
        KB_ROOT / "人工智能" / "人工智能基础.md",
        KB_ROOT / "集成电路" / "集成电路（综合）.md",
        KB_ROOT / "计算机科学与技术" / "计算机科学导论.md",
        KB_ROOT / "编程开发" / "C++.md",
    ]
    for path in stale_notes:
        if path.exists():
            path.unlink()


def ensure_category_root(base_root: Path, category: Category) -> Path:
    target = base_root / category.name
    ensure_dir(target)
    index_path = target / "目录.md"
    if not index_path.exists():
        write_text(
            index_path,
            "\n".join(
                [
                    f"# {category.name}",
                    "",
                    category.description,
                    "",
                    "- 该目录用于统一三层库的顶层分类。",
                    "",
                ]
            ),
        )
    return target


def merge_directory_contents(source: Path, target: Path) -> None:
    ensure_dir(target)
    for child in list(source.iterdir()):
        dest = target / child.name
        if child.is_dir():
            if dest.exists() and dest.is_dir():
                merge_directory_contents(child, dest)
                if child.exists() and not any(child.iterdir()):
                    child.rmdir()
            elif not dest.exists():
                child.rename(dest)
            else:
                alt = target / f"{child.stem}__merged{child.suffix}"
                child.rename(alt)
        else:
            if not dest.exists():
                child.rename(dest)
            else:
                same_size = dest.stat().st_size == child.stat().st_size
                if same_size:
                    child.unlink()
                else:
                    alt = target / f"{child.stem}__merged{child.suffix}"
                    counter = 1
                    while alt.exists():
                        alt = target / f"{child.stem}__merged_{counter}{child.suffix}"
                        counter += 1
                    child.rename(alt)
    if source.exists() and not any(source.iterdir()):
        source.rmdir()


def move_root_to_category(base_root: Path, category: str, source_name: str, target_name: str, moved: list[dict[str, str]]) -> str | None:
    source = base_root / source_name
    nested_source = base_root / category / source_name
    target = base_root / category / target_name
    if source.exists() and source != target:
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(source, target)
            moved.append({"root": str(base_root), "source": source_name, "target": f"{category}\\{target_name}", "mode": "merge"})
        else:
            source.rename(target)
            moved.append({"root": str(base_root), "source": source_name, "target": f"{category}\\{target_name}", "mode": "move"})
    elif nested_source.exists() and nested_source != target:
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(nested_source, target)
            moved.append({"root": str(base_root), "source": f"{category}\\{source_name}", "target": f"{category}\\{target_name}", "mode": "merge"})
        else:
            nested_source.rename(target)
            moved.append({"root": str(base_root), "source": f"{category}\\{source_name}", "target": f"{category}\\{target_name}", "mode": "move"})
    if target.exists():
        return f"{category}\\{target_name}"
    return None


def ensure_nested_items(target: Path, nested_items: tuple[str, ...]) -> None:
    for item in nested_items:
        ensure_dir(target / item)


def move_discrete_math_children() -> list[dict[str, str]]:
    moved: list[dict[str, str]] = []
    pairs = [
        (LIB_ROOT / "数学" / "数理逻辑", LIB_ROOT / "数学" / "离散数学" / "数理逻辑", "资料库"),
        (LIB_ROOT / "数学" / "数理逻辑入门", LIB_ROOT / "数学" / "离散数学" / "数理逻辑", "资料库"),
        (MID_ROOT / "数学" / "数理逻辑", MID_ROOT / "数学" / "离散数学" / "数理逻辑", "中间文件库"),
        (MID_ROOT / "数学" / "数理逻辑入门", MID_ROOT / "数学" / "离散数学" / "数理逻辑", "中间文件库"),
    ]
    for source, target, layer in pairs:
        if source.exists():
            ensure_dir(target.parent)
            if target.exists():
                merge_directory_contents(source, target)
                moved.append({"layer": layer, "source": str(source), "target": str(target), "mode": "merge"})
            else:
                source.rename(target)
                moved.append({"layer": layer, "source": str(source), "target": str(target), "mode": "move"})
    return moved


def merge_cross_category_alias_dirs(base_root: Path, moved: list[dict[str, str]]) -> None:
    pairs = [
        ("编程开发\\C++", "考研\\计算机专业课\\程序设计基础（C++）"),
    ]
    for source_rel, target_rel in pairs:
        source = base_root / source_rel
        target = base_root / target_rel
        if not source.exists() or source == target:
            continue
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(source, target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "merge-cross-category"})
        else:
            source.rename(target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "move-cross-category"})


def normalize_material_bucket_dirs(base_root: Path, aliases: dict[str, str], moved: list[dict[str, str]]) -> None:
    parents = [base_root] + [p for p in base_root.rglob("*") if p.is_dir()]
    parents.sort(key=lambda p: len(p.parts), reverse=True)
    for parent in parents:
        for source_name, target_name in aliases.items():
            source = parent / source_name
            target = parent / target_name
            if not source.exists() or source == target:
                continue
            ensure_dir(target.parent)
            if target.exists():
                merge_directory_contents(source, target)
                moved.append({"root": str(base_root), "source": str(source.relative_to(base_root)), "target": str(target.relative_to(base_root)), "mode": "merge-bucket-alias"})
            else:
                source.rename(target)
                moved.append({"root": str(base_root), "source": str(source.relative_to(base_root)), "target": str(target.relative_to(base_root)), "mode": "move-bucket-alias"})


def cleanup_obsolete_transition_dirs() -> None:
    obsolete_dirs = [
        LIB_ROOT / "数学" / "数学基础",
        MID_ROOT / "数学" / "数学基础",
        LIB_ROOT / "数学" / "最优化",
        MID_ROOT / "数学" / "最优化",
        LIB_ROOT / "数学" / "随机过程",
        MID_ROOT / "数学" / "随机过程",
    ]
    for path in obsolete_dirs:
        if not path.exists():
            continue
        files = [p for p in path.rglob("*") if p.is_file()]
        dirs = [p for p in path.rglob("*") if p.is_dir()]
        removable_files = all(p.name == "目录.md" for p in files)
        nonempty_dirs = [d for d in dirs if any(d.iterdir())]
        if removable_files and len(nonempty_dirs) <= 1:
            shutil.rmtree(path, ignore_errors=True)


def merge_exam_alias_dirs(base_root: Path, moved: list[dict[str, str]]) -> None:
    for source_rel, target_rel in EXAM_ALIAS_MERGES:
        source = base_root / source_rel
        target = base_root / target_rel
        if not source.exists() or source == target:
            continue
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(source, target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "merge-alias"})
        else:
            source.rename(target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "move-alias"})


def relocate_high_algebra_materials(base_root: Path, moved: list[dict[str, str]]) -> None:
    explicit_source = base_root / "考研" / "考研数学" / "高等代数"
    target = base_root / "数学" / "代数" / "高等代数"
    if explicit_source.exists():
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(explicit_source, target)
            moved.append({"root": str(base_root), "source": "考研\\考研数学\\高等代数", "target": "数学\\代数\\高等代数", "mode": "merge-high-algebra"})
        else:
            explicit_source.rename(target)
            moved.append({"root": str(base_root), "source": "考研\\考研数学\\高等代数", "target": "数学\\代数\\高等代数", "mode": "move-high-algebra"})

    source = base_root / "考研" / "考研数学" / "线性代数"
    if not source.exists():
        return

    ensure_dir(target)
    keywords = ("高等代数", "高等代数学")
    for child in list(source.iterdir()):
        if not any(keyword in child.name for keyword in keywords):
            continue
        dest = target / child.name
        if child.is_dir():
            if dest.exists() and dest.is_dir():
                merge_directory_contents(child, dest)
            elif not dest.exists():
                child.rename(dest)
            else:
                alt = target / f"{child.stem}__merged{child.suffix}"
                child.rename(alt)
        else:
            if dest.exists():
                if dest.stat().st_size == child.stat().st_size:
                    child.unlink()
                    continue
                alt = target / f"{child.stem}__moved{child.suffix}"
                counter = 1
                while alt.exists():
                    alt = target / f"{child.stem}__moved_{counter}{child.suffix}"
                    counter += 1
                child.rename(alt)
            else:
                child.rename(dest)
        moved.append({"root": str(base_root), "source": "考研\\考研数学\\线性代数", "target": "数学\\代数\\高等代数", "mode": "extract-high-algebra"})


def relocate_analysis_materials(base_root: Path, moved: list[dict[str, str]]) -> None:
    pairs = [
        ("数学\\代数\\常微分方程", "数学\\分析\\常微分方程"),
        ("数学\\代数\\偏微分方程（数学物理方法）", "数学\\分析\\偏微分方程（数学物理方法）"),
        ("数学\\代数与方程\\常微分方程", "数学\\分析\\常微分方程"),
        ("数学\\代数与方程\\偏微分方程（数学物理方法）", "数学\\分析\\偏微分方程（数学物理方法）"),
    ]
    for source_rel, target_rel in pairs:
        source = base_root / source_rel
        target = base_root / target_rel
        if not source.exists() or source == target:
            continue
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(source, target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "reclassify-analysis"})
        else:
            source.rename(target)
            moved.append({"root": str(base_root), "source": source_rel, "target": target_rel, "mode": "move-to-analysis"})


def flatten_subject_nested_dirs(base_root: Path, category: str, subject_name: str, aliases: dict[str, str], moved: list[dict[str, str]]) -> None:
    root = base_root / category / subject_name
    if not root.exists():
        return

    # 先统一根层别名目录。
    for source_name, canonical_name in aliases.items():
        source = root / source_name
        target = root / canonical_name
        if not source.exists() or source == target:
            continue
        ensure_dir(target.parent)
        if target.exists():
            merge_directory_contents(source, target)
            moved.append({"root": str(base_root), "source": f"{category}\\{subject_name}\\{source_name}", "target": f"{category}\\{subject_name}\\{canonical_name}", "mode": "merge-subject-alias"})
        else:
            source.rename(target)
            moved.append({"root": str(base_root), "source": f"{category}\\{subject_name}\\{source_name}", "target": f"{category}\\{subject_name}\\{canonical_name}", "mode": "move-subject-alias"})

    # 再把误灌进叶子课程目录里的同层学科节点提到学科根目录。
    for child in list(root.iterdir()):
        if not child.is_dir():
            continue
        for nested in list(child.iterdir()):
            if not nested.is_dir() or nested.name not in aliases:
                continue
            canonical_name = aliases[nested.name]
            target = child if canonical_name == child.name else root / canonical_name
            ensure_dir(target.parent)
            if target.exists():
                merge_directory_contents(nested, target)
                moved.append({"root": str(base_root), "source": str(nested.relative_to(base_root)), "target": str(target.relative_to(base_root)), "mode": "flatten-nested-subject"})
            else:
                nested.rename(target)
                moved.append({"root": str(base_root), "source": str(nested.relative_to(base_root)), "target": str(target.relative_to(base_root)), "mode": "move-nested-subject"})


def ensure_subject_subitems_only_at_root(base_root: Path, subject: Subject, targets: list[str]) -> list[str]:
    if not subject.subitems:
        return targets
    root_rel = f"{subject.category}\\{subject.name}"
    root = base_root / subject.category / subject.name
    if targets or root.exists() or subject.placeholder_library or subject.placeholder_middle:
        ensure_dir(root)
        ensure_nested_items(root, subject.subitems)
        if root_rel not in targets:
            targets.insert(0, root_rel)
    return targets


def ensure_subject_dir(base_root: Path, category: str, subject_name: str, subdirs: list[str], created: list[str], nested_items: tuple[str, ...]) -> str:
    target = base_root / category / subject_name
    was_missing = not target.exists()
    ensure_dir(target)
    for subdir in subdirs:
        ensure_dir(target / subdir)
    for item in nested_items:
        ensure_dir(target / item)
    index_path = target / "目录.md"
    if not index_path.exists():
        lines = [
            f"# {subject_name}",
            "",
            f"- 顶层分类：{category}",
            "- 当前状态：占位结构已创建，后续可直接补入资料。",
            "",
        ]
        if nested_items:
            lines.extend(["## 子项", *(f"- {item}" for item in nested_items), ""])
        write_text(index_path, "\n".join(lines))
    if was_missing:
        created.append(f"{category}\\{subject_name}")
    return f"{category}\\{subject_name}"


def remove_empty_named_subdirs(target: Path, names: list[str]) -> None:
    if not target.exists():
        return
    for name in names:
        child = target / name
        if child.exists() and child.is_dir():
            entries = list(child.iterdir())
            if not entries:
                child.rmdir()


def subject_note(subject: Subject, library_targets: list[str], middle_targets: list[str]) -> str:
    lines = [
        f"# {subject.name}",
        "",
        f"- 顶层分类：{subject.category}",
        f"- 原件库入口：{'、'.join(library_targets) if library_targets else '暂无'}",
        f"- 中间文件库入口：{'、'.join(middle_targets) if middle_targets else '暂无'}",
        "",
        "## 当前说明",
        subject.note or "待补充。",
        "",
    ]
    if subject.subitems:
        lines.extend(["## 结构", *(f"- {item}" for item in subject.subitems), ""])
    lines.extend(build_exam_sections(subject))
    lines.extend(
        [
            "## 网课资源",
            "- 待补充。",
            "",
            "## 当前任务",
            "- 待补充。",
            "",
        ]
    )
    return "\n".join(lines)


def build_exam_sections(subject: Subject) -> list[str]:
    if subject.name == "考研数学":
        return [
            "## 初试口径",
            "- 当前目标院校主线口径：`301 数学（一）`。",
            "- 总分 `150`，考试时长 `180` 分钟。",
            "- 学科占比：高等数学约 `56%`，线性代数约 `22%`，概率论与数理统计约 `22%`。",
            "- 常见题型：单项选择题、填空题、解答题（含证明题）。",
            "",
        ]
    if subject.name == "考研英语":
        return [
            "## 初试口径",
            "- 当前目标院校主线口径：`201 英语（一）`。",
            "- 总分 `100`，考试时长 `180` 分钟。",
            "- 常见结构：完形填空、阅读理解 A 节、新题型、英译汉、小作文、大作文。",
            "- 知识体系内部统一按能力模块组织，不再额外拆出英一/英二平行树。",
            "",
        ]
    if subject.name == "考研政治":
        return [
            "## 初试口径",
            "- 科目代码：`101 思想政治理论`。",
            "- 总分 `100`，考试时长 `180` 分钟。",
            "- 常见题型：单项选择题、多项选择题、材料分析题。",
            "",
        ]
    if subject.name == "计算机专业课":
        return [
            "## 初试口径",
            "- 北大、交大等 `408` 路线：`150` 分，常见结构为单项选择题 + 综合应用题；分值通常为数据结构 `45`、计算机组成原理 `45`、操作系统 `35`、计算机网络 `25`。",
            "- 清华 `826` 路线：按当前整理口径，模块分值为数据结构 `70`、计算机原理 `30`、操作系统 `30`、计算机网络 `20`。",
            "- 你当前内部备考口径：`408 核心 + 算法 + C++`。",
            "",
        ]
    return []


def build_root_overview(title: str, rows: list[dict[str, object]], categories: list[Category]) -> str:
    lines = [f"# {title}", "", "| 顶层分类 | 条目 | 说明 |", "| --- | --- | --- |"]
    for category in categories:
        children = [row["name"] for row in rows if row["category"] == category.name]
        child_text = " / ".join(children) if children else "暂无"
        lines.append(f"| {category.name} | {child_text} | {category.description} |")
    lines.append("")
    return "\n".join(lines)


def build_kb_home(rows: list[dict[str, object]]) -> str:
    lines = [
        "# SJTU AI 培养计划与课程体系",
        "",
        "- 三层总原则：原件库 / 中间文件库 / 知识体系共用同一套顶层分类。",
        "- 知识体系当前只保留：`考研 / 数学 / 物理 / 计算机科学与技术 / 编程开发 / 人工智能 / 集成电路 / 电气工程与自动化 / 通信工程`。",
        "- 明确排除：`Calibre书库 / 大学英语 / 高中 / 其他`。",
        "",
        "## 顶层入口",
    ]
    for category in CATEGORIES:
        if category.include_in_kb:
            lines.append(f"- [[{category.name}\\总览]]")
    lines.extend(
        [
            "- [[90-排除与存档]]",
            "",
            "## 考研分类规则",
            "- `考研` 只保留初试主线：考研数学、考研英语、考研政治、计算机专业课。",
            "- 卷种代码（如数学一、英语一、408、826）只保留为目标院校映射标签，不再拆成平行知识树。",
            "- 复试不单列到知识体系主结构中。",
            "",
        ]
    )
    return "\n".join(lines)


def build_category_note(category: Category, rows: list[dict[str, object]]) -> str:
    lines = [f"# {category.name}", "", category.description, "", "| 条目 | 原件库 | 中间文件库 |", "| --- | --- | --- |"]
    for row in rows:
        if row["category"] != category.name or not row["kb_include"]:
            continue
        lib_text = " / ".join(row["library_targets"]) if row["library_targets"] else "暂无"
        mid_text = " / ".join(row["middle_targets"]) if row["middle_targets"] else "暂无"
        lines.append(f"| [[{safe_name(row['name'])}]] | {lib_text} | {mid_text} |")
    lines.append("")
    return "\n".join(lines)


def build_excluded_note() -> str:
    lines = [
        "# 排除与存档",
        "",
        "- 以下顶层分类保留在资料体系中，但不进入知识体系主结构。",
        "",
        "## 明确排除",
        "- Calibre书库",
        "- 大学英语",
        "- 高中",
        "- 其他",
        "",
        "## 实体桌面当前保留项",
    ]
    lines.extend(f"- {item}" for item in PHYSICAL_DESKTOP_RETAIN)
    lines.append("")
    return "\n".join(lines)


def build_report(rows: list[dict[str, object]], moved_lib: list[dict[str, str]], moved_mid: list[dict[str, str]], created_lib: list[str], created_mid: list[str]) -> str:
    lines = [
        "# 课程体系三层库搭建报告",
        "",
        "- 日期：2026-03-14",
        "- 当前规则：原件库与中间文件库按实体桌面顶层分类；知识体系排除 `Calibre书库 / 大学英语 / 高中 / 其他`。",
        "- 数学顶层当前按实体桌面大类组织：`分析 / 代数 / 几何与拓扑 / 概率与统计 / 规划与优化 / 离散数学`。",
        "- 考研顶层当前只纳入初试：`考研数学 / 考研英语 / 考研政治 / 计算机专业课`；`程序设计基础（C++）/ 数据结构 / 算法设计与分析 / 操作系统 / 计算机网络 / 计算机组成原理` 统一归到 `考研\\计算机专业课` 下，`计算机体系结构` 单独保留在 `计算机科学与技术` 下。",
        "- 学科树补充策略：按用户当前研究方向做选择性扩展，优先补 `视觉 / 世界模型 / 具身智能 / 大模型工程` 相关节点，不追求一次性补齐所有课程。",
        "- 待确认删除区：本轮保留，不清空。",
        "",
        "## 原件库移动记录",
    ]
    if moved_lib:
        lines.extend(f"- `{item['source']}` -> `{item['target']}`" for item in moved_lib)
    else:
        lines.append("- 无。")
    lines.extend(["", "## 中间文件库移动记录"])
    if moved_mid:
        lines.extend(f"- `{item['source']}` -> `{item['target']}`" for item in moved_mid)
    else:
        lines.append("- 无。")
    lines.extend(["", "## 新建占位课程位（原件库）"])
    if created_lib:
        lines.extend(f"- {item}" for item in created_lib)
    else:
        lines.append("- 无新增。")
    lines.extend(["", "## 新建占位课程位（中间文件库）"])
    if created_mid:
        lines.extend(f"- {item}" for item in created_mid)
    else:
        lines.append("- 无新增。")
    lines.extend(["", "## 课程现状", "| 条目 | 顶层分类 | 原件库 | 中间文件库 | 是否进入知识体系 | 备注 |", "| --- | --- | --- | --- | --- | --- |"])
    for row in rows:
        lib_text = " / ".join(row["library_targets"]) if row["library_targets"] else "暂无"
        mid_text = " / ".join(row["middle_targets"]) if row["middle_targets"] else "暂无"
        kb_text = "是" if row["kb_include"] else "否"
        lines.append(f"| {row['name']} | {row['category']} | {lib_text} | {mid_text} | {kb_text} | {row['note']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ensure_dir(REPORT_ROOT)
    cleanup_previous_generated_notes()

    for category in CATEGORIES:
        ensure_category_root(LIB_ROOT, category)
        if category.name not in EXCLUDED_MID_CATEGORIES:
            ensure_category_root(MID_ROOT, category)

    moved_lib: list[dict[str, str]] = []
    moved_mid: list[dict[str, str]] = []
    created_lib: list[str] = []
    created_mid: list[str] = []
    rows: list[dict[str, object]] = []

    for subject in SUBJECTS:
        library_targets = [ref for ref in subject.library_refs if (LIB_ROOT / ref).exists()]
        middle_targets = [ref for ref in subject.middle_refs if (MID_ROOT / ref).exists()]

        for source_name, target_name in subject.library_sources:
            result = move_root_to_category(LIB_ROOT, subject.category, source_name, target_name, moved_lib)
            if result:
                library_targets.append(result)

        for source_name, target_name in subject.middle_sources:
            result = move_root_to_category(MID_ROOT, subject.category, source_name, target_name, moved_mid)
            if result:
                middle_targets.append(result)

        if subject.placeholder_library and not library_targets and subject.library_sources:
            target_name = subject.library_sources[0][1]
            library_targets.append(
                ensure_subject_dir(
                    LIB_ROOT,
                    subject.category,
                    target_name,
                    LIB_SUBDIRS if subject.scaffold_library_subdirs else [],
                    created_lib,
                    subject.subitems,
                )
            )

        if subject.placeholder_middle and not middle_targets and subject.middle_sources:
            target_name = subject.middle_sources[0][1]
            middle_targets.append(
                ensure_subject_dir(
                    MID_ROOT,
                    subject.category,
                    target_name,
                    MID_SUBDIRS if subject.scaffold_middle_subdirs else [],
                    created_mid,
                    subject.subitems,
                )
            )

        library_targets = ensure_subject_subitems_only_at_root(LIB_ROOT, subject, library_targets)
        middle_targets = ensure_subject_subitems_only_at_root(MID_ROOT, subject, middle_targets)

        root_lib = LIB_ROOT / subject.category / subject.name
        root_mid = MID_ROOT / subject.category / subject.name
        if subject.subitems and not subject.scaffold_library_subdirs and root_lib.exists():
            remove_empty_named_subdirs(root_lib, LIB_SUBDIRS)
        if subject.subitems and not subject.scaffold_middle_subdirs and root_mid.exists():
            remove_empty_named_subdirs(root_mid, MID_SUBDIRS)

        library_targets = dedupe_keep_order(library_targets)
        middle_targets = dedupe_keep_order(middle_targets)

        rows.append(
            {
                "name": subject.name,
                "category": subject.category,
                "kb_include": subject.kb_include and subject.category not in EXCLUDED_KB_CATEGORIES,
                "library_targets": library_targets,
                "middle_targets": middle_targets,
                "note": subject.note,
            }
        )

    discrete_moved = move_discrete_math_children()
    if discrete_moved:
        for item in rows:
            if item["name"] == "离散数学":
                library_targets = list(item["library_targets"])
                middle_targets = list(item["middle_targets"])
                if any(entry["layer"] == "资料库" for entry in discrete_moved):
                    if "数学\\离散数学" not in library_targets:
                        library_targets.append("数学\\离散数学")
                if any(entry["layer"] == "中间文件库" for entry in discrete_moved):
                    if "数学\\离散数学" not in middle_targets:
                        middle_targets.append("数学\\离散数学")
                item["library_targets"] = library_targets
                item["middle_targets"] = middle_targets

    cleanup_obsolete_transition_dirs()
    merge_exam_alias_dirs(LIB_ROOT, moved_lib)
    merge_exam_alias_dirs(MID_ROOT, moved_mid)
    merge_cross_category_alias_dirs(LIB_ROOT, moved_lib)
    merge_cross_category_alias_dirs(MID_ROOT, moved_mid)
    relocate_high_algebra_materials(LIB_ROOT, moved_lib)
    relocate_high_algebra_materials(MID_ROOT, moved_mid)
    relocate_analysis_materials(LIB_ROOT, moved_lib)
    relocate_analysis_materials(MID_ROOT, moved_mid)
    normalize_material_bucket_dirs(LIB_ROOT, LIB_BUCKET_ALIASES, moved_lib)
    for (category, subject_name), aliases in SUBJECT_SUBITEM_ALIASES.items():
        flatten_subject_nested_dirs(LIB_ROOT, category, subject_name, aliases, moved_lib)
        flatten_subject_nested_dirs(MID_ROOT, category, subject_name, aliases, moved_mid)

    write_text(LIB_ROOT / "00-分类总览.md", build_root_overview("资料库分类总览", rows, CATEGORIES))
    write_text(MID_ROOT / "00-分类总览.md", build_root_overview("中间文件库分类总览", rows, [category for category in CATEGORIES if category.name not in EXCLUDED_MID_CATEGORIES]))

    ensure_dir(KB_ROOT)
    for category in CATEGORIES:
        if not category.include_in_kb:
            continue
        category_dir = KB_ROOT / category.name
        ensure_dir(category_dir)
        write_text(category_dir / "总览.md", build_category_note(category, rows))
        for subject in SUBJECTS:
            if subject.category == category.name and subject.kb_include:
                row = next(item for item in rows if item["name"] == subject.name)
                write_text(
                    category_dir / f"{safe_name(subject.name)}.md",
                    subject_note(subject, row["library_targets"], row["middle_targets"]),
                )

    write_text(KB_ROOT / "Home.md", build_kb_home(rows))
    write_text(KB_ROOT / "90-排除与存档.md", build_excluded_note())
    write_text(REPORT_PATH, build_report(rows, moved_lib, moved_mid, created_lib, created_mid))
    JSON_REPORT_PATH.write_text(
        json.dumps(
            {
                "moved_library": moved_lib,
                "moved_middle": moved_mid,
                "moved_discrete_math_children": discrete_moved,
                "created_library": created_lib,
                "created_middle": created_mid,
                "rows": rows,
                "pending_delete_action": "kept",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for old_file in [LIB_ROOT / "00-课程总览.md", MID_ROOT / "00-OCR课程总览.md"]:
        if old_file.exists():
            old_file.unlink()


if __name__ == "__main__":
    main()
