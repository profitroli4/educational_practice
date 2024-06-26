import requests
import psycopg2
import json

def fetch_job_listings(job_title, page=0, per_page=10):
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
        job_listings = []

        for item in data['items']:
            job_listings.append({
                'hh_id': item.get('id'),
                'title': item.get('name'),
                'link': item.get('alternate_url'),
                'employer': item.get('employer', {}).get('name'),
                'salary': item.get('salary'),
                'date_posted': item.get('published_at'),
                'description': item.get('snippet', {}).get('responsibility'),
                'requirements': item.get('snippet', {}).get('requirement')
            })
        return job_listings, data.get('pages', 0)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return [], 0

def save_job_listings_to_json(job_listings, filename='job_listings.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(job_listings, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    job_title = input("Введите наименование профессии для поиска вакансий: ")
    page = 0
    per_page = 10
    while True:
        job_listings, total_pages = fetch_job_listings(job_title, page, per_page)
        if job_listings:
            save_job_listings_to_json(job_listings)
            print(f"Сохранено {len(job_listings)} вакансий на странице {page + 1} из {total_pages}")

            if page < total_pages - 1:
                next_page = input("Введите 'n' для загрузки следующей страницы, или любой другой символ для завершения: ")
                if next_page.lower() == 'n':
                    page += 1
                else:
                    break
            else:
                print("Все страницы загружены.")
                break
        else:
            print("Не удалось найти вакансии по указанной профессии.")
            break
