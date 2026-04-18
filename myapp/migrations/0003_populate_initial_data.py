from django.db import migrations

def populate_data(apps, schema_editor):
    AppSetting = apps.get_model('myapp', 'AppSetting')
    Feature = apps.get_model('myapp', 'Feature')
    Statistic = apps.get_model('myapp', 'Statistic')
    Testimonial = apps.get_model('myapp', 'Testimonial')
    Template = apps.get_model('myapp', 'Template')

    # App Settings
    settings = [
        ('app_name', 'The Engineering Editorial'),
        ('app_version', 'V2.4.0'),
        ('hero_title', 'Turn your notes into LaTeX without the headache'),
        ('hero_subtitle', 'We take your drafts, PDFs, or photos of your notes and turn them into clean, professional LaTeX files so you don\'t have to.'),
        ('template_section_title', 'Start with a template'),
        ('template_section_subtitle', 'Pick a layout that fits your project and we\'ll handle the rest.'),
        ('footer_description', 'Simple tools for researchers. Built to make formatting easier.'),
    ]
    for key, value in settings:
        AppSetting.objects.update_or_create(key=key, defaults={'value': value})

    # Features
    features = [
        ('Real-time view', 'Watch your notes turn into a formatted document on the right side of your screen as you work.', 'visibility', 1),
        ('Smart formatting', 'We\'ll figure out where your headers, lists, and tables should go so the code looks exactly right.', 'auto_awesome', 2),
        ('One-click download', 'Download everything you need in one zip file, including the source code and your figures.', 'download', 3),
    ]
    for title, desc, icon, order in features:
        Feature.objects.update_or_create(title=title, defaults={'description': desc, 'icon': icon, 'order': order})

    # Statistics
    stats = [
        ('Papers finished', '15k+', 'Total research papers created using our templates.', 1),
        ('Successful builds', '99.9%', 'Percentage of documents that compile perfectly on the first try.', 2),
    ]
    for label, value, desc, order in stats:
        Statistic.objects.update_or_create(label=label, defaults={'value': value, 'description': desc, 'order': order})

    # Testimonial
    Testimonial.objects.update_or_create(
        name='Dr. Elena Rostova',
        defaults={
            'role': 'Physics Researcher',
            'quote': 'It cut my work time in half. It\'s much easier than writing all the math by hand.',
            'image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuBRc_j-a-vwdkVznB6ziMlKL3BjB_aAcBtlmqQp8JYvX1lPsyX7oVWXU1BY3T33jSZYUsk1s2C9hM6zMlWb5wlgqxuL6pJTNSQfWcKDPvMeuBuhmu_6k35AnjgpGK7wgV7WXzGjDYYwgsuM-kdsw-P4zrrwhD972Z7omJAg3uqU4JRPWdK1Uo9TJo2HcLOu06XoHA8WDh3XTlFdI71me0kYUJsJNQtObcp8X8l8RiTm9jq7-MZtv2IBgmg0Izgq6Ls-ZW3e1BU32g'
        }
    )

    # Default Templates
    templates = [
        ('Academic Paper', 'Academic', 'https://lh3.googleusercontent.com/aida-public/AB6AXuALvqWctkNaGa8f9xghtCSee0YOFS5pLw0Eb7LFJCet3PlB-jFVOTRJEe0yWbGb3adtZM2qaZmy1Lu5nza6DGaY4bEUKaUnuugAYTb7Lx7YxPOf8TMQsTMWoj7XCEjcJI3ncuowQwwrrRwaq3vJUlhRA5c2zaFXggWCTOVuo5IYQQFc1bOvbgE9Nbhrg7SeevmewPFvsKgWHnP-TN0j4MfcvAOz6gXCrsqNpZ6Ox_Mzu7yZEsmfo3LOy5gDynk01j0I0LYZrADFzQ', r'\documentclass{article}\n\begin{document}\nAcademic Paper\n\end{document}'),
        ('Modern Resume', 'Professional', 'https://lh3.googleusercontent.com/aida-public/AB6AXuCspSbGMYfJG_mjVi6g8mBwmpWcm9Dz4VM_CrDh6cdcyVGzNXdPxYHCss_uJ5KM_5_TPXOCKg_gYd27FkODu2D27YNjDvI-qP1tOp50yjwS-Px1j6ghNN0B62tdqvA9QDcMywfdc6ajpNx2D29TjsrlBUwDvVCUbPqdd5oyeH9xt1xIuPOuz8IH-bso-Z9JZQMKuhidlxaoNqYEk7HedVIznJeggqGIWhXRYc3qAk_hnHKMw1y5HdQWSQSWVA5WVbm2RdrW2t9UUg', r'\documentclass{article}\n\begin{document}\nResume\n\end{document}'),
        ('Presentation', 'Academic', 'https://lh3.googleusercontent.com/aida-public/AB6AXuBXNW6n4PV9-9p9HqMrUrJiPW2bxB4UWBZrDf9SxhtVuwoASP4ladmvkOp-PgiIvOS-fzhnb6Swz6pY_v4Zy1_5lsRaxLRvC3E9RW0EuEz4ktno2LMxoJWuNNIePxTkHFg39r2IyWPxOJuwHWByv4t2aT2wG7mtHPRYXEAdSJxgNydzMntA_WumhW9BkiPibF60ZI1AbESAotXTNdIBAtzOWUA6YWwNi8dqTO54Qr0lqCizt9Obwo7pz9kfgrcdyhYjguQD9Hv4Wg', r'\documentclass{beamer}\n\begin{document}\nPresentation\n\end{document}'),
        ('Full Book', 'Professional', 'https://lh3.googleusercontent.com/aida-public/AB6AXuCSlYhbTt8w5ISmjQnVZQvmzkwYzyvX6peTtKQ9ZOkLDVdZYCXF0BHPuoFQEk5AfqgRmof8vGfFUsJCfNG0NH5snubgLPIpRMXJ0I8dnCNH2PEr86bhqHBOaQuhnUPdT4M7GTpShJpf2csof5TlceYkIbPA0O8oB3cycWdX3hqV4KuIo43qclpKNvuKrzzcBwbIZ4aIdQFqcjQYbJkZT5RHAley0hyiL71uwEvZDSLT0QnHgRSgle3SBfvDyJLZAoR2o2RLBBJK4w', r'\documentclass{book}\n\begin{document}\nBook\n\end{document}'),
    ]
    for name, cat, img, content in templates:
        Template.objects.get_or_create(name=name, defaults={'category': cat, 'image_url': img, 'content': content})

class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0002_appsetting_feature_statistic_testimonial'),
    ]

    operations = [
        migrations.RunPython(populate_data),
    ]
