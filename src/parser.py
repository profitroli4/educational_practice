import re
import requests

def remove_html_tags(text):
    if text is None:
        return ''
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def fetch_job_listings(job_title, page=0, per_page=10):
    """Парсер для API hh.ru"""
    url = "https://api.hh.ru/vacancies"
    params = {
        'text': job_title,
        'page': page,
        'per_page': per_page
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        vacancies = []
        for item in data['items']:
            # Убираем декорации текста
            description = remove_html_tags(item.get('snippet', {}).get('responsibility', ''))
            requirements = remove_html_tags(item.get('snippet', {}).get('requirement', ''))

            salary_info = item.get('salary')

            vacancies.append({
                'hh_id': item.get('id'),
                'title': item.get('name'),
                'link': item.get('alternate_url'),
                'employer': item.get('employer', {}).get('name'),
                'salary': salary_info if salary_info else {},
                'date_posted': item.get('published_at'),
                'description': description,
                'requirements': requirements
            })

        total_pages = data.get('pages', 1)
        return vacancies, total_pages
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return [], 0