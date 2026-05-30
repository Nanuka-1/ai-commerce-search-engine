TRANSLATIONS = {

    "ka": {
        "greeting": "გამარჯობა! როგორ შემიძლია დაგეხმაროთ?",
        "empty": "გთხოვთ, შეიყვანოთ საძიებო მოთხოვნა",
        "unknown": "ვერ გავიგე თქვენი მოთხოვნა",
        "sku_not_found": "ამ SKU კოდით პროდუქტი ვერ მოიძებნა",
        "price_invalid_sku": "ფასის შესამოწმებლად გთხოვთ მიუთითოთ სწორი SKU",
        "price_missing_identifier": "ფასის შესამოწმებლად, გთხოვთ მოგვწეროთ პროდუქტის ზუსტი დასახელება, SKU/არტიკული ან მოგვიგზავნოთ ფოტო",
        "too_many_results_refine": "მოვიძიე რამდენიმე შესაბამისი პროდუქტი. გთხოვთ დააზუსტოთ მოდელი, კატეგორია ან პროდუქტის ტიპი.",
        "sku_size_confirm": "ვიპოვე პროდუქტი კოდით {sku}. სწორად გავიგე, რომ გჭირდებათ ზომა {size}?",
        "sku_ask_size": "ვიპოვე პროდუქტი კოდით {sku}. გთხოვთ, მიუთითოთ რომელი ზომა გჭირდებათ."
    },
    "en": {
        "greeting": "Hello! How can I help you today?",
        "empty": "Please enter a search query",
        "unknown": "Sorry, I could not understand your request",
        "sku_not_found": "Product with this SKU was not found",
        "price_invalid_sku": "Please provide a valid SKU for price check",
        "price_missing_identifier": "To check the price, please send the exact product name, SKU, or a photo of the item",
        "too_many_results_refine": "I found several matching products. Please specify the model, category, or type of item.",
        "sku_size_confirm": "I found the product with code {sku}. Just to confirm, are you looking for size {size}?",
        "sku_ask_size": "I found the product with code {sku}. Please let me know which size you need."
    }
}


def translate(key: str, locale: str) -> str:
    lang = locale if locale in TRANSLATIONS else "ka"
    return TRANSLATIONS[lang].get(key, key)


def translate(key: str, locale: str) -> str:
    lang = locale if locale in TRANSLATIONS else "ka"
    return TRANSLATIONS[lang].get(key, key)