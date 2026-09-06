# قاعدة بيانات البرومبتات

ضع كل Prompt في ملف مستقل داخل هذا المجلد، ويفضل استخدام القالب الموحد التالي:

```yaml
id: unique-id
title: "عنوان البرومبت"
category: image|video|content|business|education|construction|coding|other
tool: "اسم الأداة"
tags: []
goal: "الهدف"
language: ar|en|both
source: "اسم المصدر"
source_url: "الرابط"
added_at: "YYYY-MM-DD"
quality: unreviewed|reviewed|featured
```

ثم يُكتب نص البرومبت وملاحظات الاستخدام والحقول القابلة للاستبدال.
