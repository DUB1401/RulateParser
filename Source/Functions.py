from dublib.WebRequestor import WebRequestor

import logging

def Autorizate(Requestor: WebRequestor, Settings: dict) -> bool:
	# Состояние: успешна ли авторизация.
	IsSuccess = False
	# Заголовки.
	Headers = {
		"Origin": "https://tl.rulate.ru",
		"Referer": "https://tl.rulate.ru",
		"Content-Type": "application/x-www-form-urlencoded"
	}
	# Преобразование данных авторизации в тело запроса.
	AuthData = "login%5Blogin%5D=" + Settings["login"] + "&login%5Bpass%5D=" + Settings["password"]
	# Выполнение запроса на авторизацию.
	Response = Requestor.post("https://tl.rulate.ru", headers = Headers, data = AuthData)
	# Если запрос успешен, переключить статус.
	if Response.status_code == 200: IsSuccess = True
	
	# Если запросы слишком частые.
	if "Вы совершили слишком много попыток входа. Подождите 10 минут." in Response.text:
		# Запись в лог критической ошибки: слишком много попыток входа.
		logging.critical("Too many login attempts. Wait 10 minutes.")
		# Завершение работы.
		exit(1)
		
	return IsSuccess

def EnableMature(Requestor: WebRequestor, Settings: dict) -> bool:
	# Состояние: успешно ли включение 18+ контента.
	IsSuccess = False
	# Заголовки.
	Headers = {
		"Origin": "https://tl.rulate.ru",
		"Referer": "https://tl.rulate.ru",
		"Content-Type": "application/x-www-form-urlencoded"
	}
	# Данные запроса.
	Data = "path=%2Fbook%2F" + str(Settings["mature-book-id"]) + "&ok=%D0%94%D0%B0"
	# Выполнение запросов.
	Response = Requestor.get("https://tl.rulate.ru/mature?path=%2Fbook%2F" + str(Settings["mature-book-id"]))
	Response = Requestor.post("https://tl.rulate.ru/mature?path=%2Fbook%2F" + str(Settings["mature-book-id"]), headers = Headers, data = Data)
	# Если запрос успешен, переключить статус.
	if Response.status_code == 200: IsSuccess = True
		
	return IsSuccess

def ToFixedFloat(FloatNumber: float, Digits: int = 0) -> float:
	return float(f"{FloatNumber:.{Digits}f}")

def SecondsToTimeString(Seconds: float) -> str:
	# Количество часов.
	Hours = int(Seconds / 3600.0)
	Seconds -= Hours * 3600
	# Количество минут.
	Minutes = int(Seconds / 60.0)
	Seconds -= Minutes * 60
	# Количество секунд.
	Seconds = ToFixedFloat(Seconds, 2)
	# Строка-дескриптор времени.
	TimeString = ""

	# Генерация строки.
	if Hours > 0:
		TimeString += str(Hours) + " hours "
	if Minutes > 0:
		TimeString += str(Minutes) + " minutes "
	if Seconds > 0:
		TimeString += str(Seconds) + " seconds"

	return TimeString

#==========================================================================================#
# >>>>> ЭКСПЕРИМЕНТАЛЬНЫЕ ФУНКЦИИ DUBLIB <<<<< #
#==========================================================================================#

def IsNotAlpha(text: str) -> bool:
	"""
	Проверяет, состоит ли строка целиком из небуквенных символов.
	"""

	# Результат проверки.
	Result = True

	# Для каждого символа в строке.
	for Character in text:

		# Если символ является буквой.
		if Character.isalpha():
			# Изменение результата.
			Result = False
			# Прерывание цикла.
			break

	return Result

def StripAlpha(text: str) -> str:
	"""
	Удаляет начальные и конечные небуквенные символы.
		text – обрабатываемая строка.
	"""

	try:
		# Пока по краям строки есть небуквенные символы, удалять их по одному.
		while not text[0].isalpha(): text.pop(0)
		while not text[-1].isalpha(): text.pop()

	except:
		# Очистка строки.
		text = ""

def Zerotify(value: any) -> any:
	"""
	Преобразует значения, логически интерпретируемые в False, в тип None.
		value – обрабатываемое значение.
	"""

	# Если значение логически интерпретируется в False, обнулить его.
	if bool(value) == False: value = None

	return value