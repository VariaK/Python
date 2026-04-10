import requests

cookies = {

}

headers = {

}

params = {
    'page_id': '1',
    'page_size': '12',
}

response = requests.get(
    'https://www.tirabeauty.com/ext/plpoffers/application/api/v1.0/collections/makeup-face/items',
    params=params,
    cookies=cookies,
    headers=headers,
)

data = response.json()
items = data.get('items', [])

for item in items:
    name = item.get('name', 'No name')
    price = item.get('price', {}).get('effective', {}).get('min', 'N/A')
    custom_json = item.get('_custom_json', {})
    rating = custom_json.get('averageRating', 'No rating')
    reviews_count = custom_json.get('reviewsCount', '0')
    
    print(f"Product: {name}\nPrice: ₹{price}\nRating: {rating}/5 ({reviews_count} reviews)\n" + "-" * 40)
