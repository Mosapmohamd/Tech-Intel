# Tech Intelligence Agent

المواصفات الكاملة في @docs/SPEC.md — اقرأها قبل أي شغل.

## قواعد العمل

- المشروع بيتبني على 12 phase بالترتيب حسب SPEC.md. متعديش أي phase.
- استنى موافقتي قبل ما تبدأ أي phase جديدة.
- آخر كل phase: اشرح قرارات التصميم، اعرض شجرة الملفات المتغيرة، وقولي أزاي أختبرها.
- حدّث قسم "حالة المشروع" تحت في نفس commit الـ phase.

## اللغة

- كل الكود والتعليقات والـ docstrings وأسماء المتغيرات بالإنجليزي.
- مخرجات الـ LLM الموجّهة للمستخدم (الملخصات، التقارير، الإيميل) بالعربي.
- كلّمني بالعربي.

## معايير الجودة

لازم الأربعة يعدّوا قبل أي commit:

```bash
pytest -q
ruff check app tests main.py
black --check app tests main.py
mypy app main.py
```

mypy شغّال بـ `strict = true`. متضيفش `# type: ignore` من غير سبب مكتوب.

## حالة المشروع

- ✅ **Phase 1** — هيكل المشروع، CLI skeleton بـ 10 أوامر، pyproject + tooling
- ✅ **Phase 2** — قاعدة البيانات: 11 جدول، 10 repositories، bootstrap + stats، 20 اختبار
- ✅ **Phase 3** — RSS collectors: sources.yaml بـ26 مصدر، FeedClient بـconditional GET، parser، CollectorAgent، 75 اختبار
- ⬜ **Phase 4** — استخراج المحتوى (trafilatura) ← **التالي**
- ⬜ Phase 5 إزالة تكرار · 6 تقييم · 7 Ollama · 8 تقارير
- ⬜ Phase 9 إيميل HTML · 10 scheduler · 11 اختبارات · 12 توثيق

## قرارات معمارية مهمة

- **المقالات المكررة بتتربط مش بتتمسح.** `Article.duplicate_of_id` بيربط النسخة
  بالأصل و`mention_count` بيزيد. ده اللي هيغذّي مكوّن *cross-source mentions*
  في محرك التقييم (Phase 6). لو مسحنا المكرر هنخسر الإشارة دي.
- **هاشين للتكرار:** `url_hash` (unique) لنفس اللينك، `content_hash` للمحتوى
  المنشور بلينكات مختلفة عبر مصادر مختلفة.
- **كل مكوّنات الـ score بتتخزن منفصلة** + `weights_snapshot` (JSON). يعني نقدر
  نعدّل الأوزان ونعيد الحساب من غير ما نشغّل الـ LLM تاني.
- **الـ agents ما بتلمسش SQLAlchemy.** كل وصول للبيانات عبر `app/core/repositories/`.
  ده اللي بيخلي الـ agents قابلة للاختبار بقاعدة بيانات مؤقتة.
- **User-Agent شبه المتصفح.** بعض الـ CDNs (Cloudflare) بترجّع 403 لأي
  User-Agent واضح إنه بوت. الافتراضي دلوقتي Mozilla/5.0 وقابل للتغيير.
- **`check-feeds`** بيفحص صحة كل الفيدات في ثواني من غير ما يخزّن حاجة —
  استخدمه بعد أي تعديل على sources.yaml.
- **الـ retry بيفرّق بين مؤقت ودائم.** 4xx بيفشل فورًا (403 مش هيتصلح بإعادة
  محاولة)؛ 408/429/5xx بس اللي بيتعاد. شوف `TRANSIENT_STATUSES`.
- **`sources.yaml` هو مصدر الحقيقة للمصادر.** الترتيب: قيمة المصدر > افتراضي
  المجموعة > `defaults` العام. `add-source` بيكتب في الملف الأول بعدين القاعدة.
- **الـ prompts ملفات جوّه `app/prompts/`** — ممنوع أي prompt مكتوب جوّه الكود.
- **كل مخرجات الـ LLM فيها provenance** (`model_name`, `prompt_version`,
  `generation_seconds`) عشان نعيد توليد السجلات القديمة لما نغيّر prompt.
- **SQLite:** `foreign_keys=ON` مفعّلة يدويًا (SQLite بيقفلها افتراضيًا) و
  `journal_mode=WAL` عشان الـ scheduler يقرأ والـ pipeline بيكتب.
- **الإعدادات كلها من `Settings`** (`app/core/config/settings.py`) بـ prefix
  `TIA_`. ممنوع `os.environ` في أي مكان تاني. المسارات النسبية بتتربط بجذر
  المشروع مش بمجلد التشغيل.

## أوامر شائعة

```bash
uv pip install -e ".[dev]"
python main.py rebuild-db --force   # يبني الجداول ويزرع الـ 15 تصنيف
python main.py stats                # إحصائيات القاعدة
python main.py check-feeds          # يفحص صحة كل الفيدات
python main.py --help               # كل الأوامر
```

## ملفات ممنوع ترفعها

`.env`، `data/*.db`، `logs/` — كلها في `.gitignore` بالفعل. متضيفهاش يدويًا.
