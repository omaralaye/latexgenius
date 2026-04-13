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
        ('hero_title', 'Convert Any Document to LaTeX in Seconds'),
        ('hero_subtitle', 'Bridge the gap between draft and publication. Our AI-driven engine preserves complex equations, nested citations, and intricate layouts with editorial precision.'),
        ('template_section_title', 'The Precision Templates'),
        ('template_section_subtitle', 'Standardize your output with high-performance templates designed for the world\'s leading journals and institutions.'),
        ('footer_description', 'Setting the standard for technical precision. Document conversion built by engineers, for engineers.'),
    ]
    for key, value in settings:
        AppSetting.objects.update_or_create(key=key, defaults={'value': value})

    # Features
    features = [
        ('Real-time Preview', 'Watch your source document transform into a compile-ready PDF in a live, split-pane environment with zero lag.', 'speed', 1),
        ('AI-Powered Parsing', 'Our custom neural network understands the semantics of your document, ensuring headers, lists, and tables map perfectly to LaTeX syntax.', 'psychology', 2),
        ('One-Click Export', 'Download a clean .zip package containing the .tex source, bibliography files, and high-resolution figures in one go.', 'download_done', 3),
    ]
    for title, desc, icon, order in features:
        Feature.objects.update_or_create(title=title, defaults={'description': desc, 'icon': icon, 'order': order})

    # Statistics
    stats = [
        ('Research papers published', '15k+', 'Research papers published using our standard journal template.', 1),
        ('Compilation success rate', '99.9%', 'Compilation success rate for complex LaTeX-heavy bibliographies.', 2),
    ]
    for label, value, desc, order in stats:
        Statistic.objects.update_or_create(label=label, defaults={'value': value, 'description': desc, 'order': order})

    # Testimonial
    Testimonial.objects.update_or_create(
        name='Arthur P. Vance',
        defaults={
            'role': 'Lead Systems Architect, TexPrecision',
            'quote': 'Precision is not an afterthought; it is the infrastructure upon which technical credibility is built.',
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
