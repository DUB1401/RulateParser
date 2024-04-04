from dublib.Methods import CheckForCyrillicPresence, Cls, ReadJSON, RemoveRecurringSubstrings, WriteJSON
from dublib.WebRequestor import WebRequestor
from Source.Functions import IsNotAlpha
from dublib.Polyglot import HTML
from bs4 import BeautifulSoup
from time import sleep
from PIL import Image

import requests
import enchant
import logging
import os
import re

class Parser:
	
	#==========================================================================================#
	# >>>>> ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#
	
	def __CheckForLinkParagraph(self, Paragraph: str) -> bool:
		# Поиск ссылки.
		Match = re.search("(http|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])", Paragraph)
		# Возвращаемый результат.
		Result = False
		# Если ссылка найдена и является абзацем, удалить её.
		if Match and Match[0] == Paragraph: Result = True
		
		return Result
	
	def __DetermineImageType(self, Path: str, ChapterID: int | str) -> str | None:
		# Тип файла.
		Type = None
		# Имя файла.
		Filename = Path.split("/")[-1]
		
		try:
			# Чтение файла и определение формата.
			ImageFile = Image.open(Path)
			Type = ImageFile.format.lower()
			
		except:
			# Запись в лог ошибки: не удалось определить тип изображения.
			logging.error(f"Novel: {self.__ID}. Chapter: {ChapterID}. Unable to determine image type: \"{Filename}\".")
		
		return Type

	def __DownloadImage(self, Link: str, ChapterID: int | str, ImageIndex : int | str) -> str:
		# Директория загрузки.
		Directory = self.__Settings["images-directory"] + f"/{self.__ID}/{ChapterID}"
		# Если директория не существует, создать.
		if not os.path.exists(Directory): os.makedirs(Directory)
		# Список файлов в папке.
		Files = os.listdir(self.__Settings["images-directory"] + f"/{self.__ID}/{ChapterID}")
		# Для каждого названия файла удалить расширение.
		for Index in range(len(Files)): Files[Index] = "".join(Files[Index].split(".")[:-1])
		
		# Если ссылка ведёт на сервер сайта, добавить домен.
		if Link.startswith("/"): Link = f"https://tl.rulate.ru/{Link}"
		# Оригинальное имя файла.
		OriginalFilename = Link.split("/")[-1].split("?")[0]
		# Тип файла.
		FileType = ""
		# Если оригинальное имя файла содержит точку, получить расширение файла.
		if "." in OriginalFilename: FileType = "." + OriginalFilename.split(".")[-1]
		# Имя файла.
		Filename = f"{ChapterID}_{ImageIndex}"
		
		# Если файл ещё не загружен.
		if Filename not in Files:
			# Добавление расширения к имени файла.
			Filename += FileType
			
			try:
				# Выполнение запроса.
				Response = requests.get(Link)
		
				# Если запрос успешен.
				if Response.status_code == 200:

					# Открытие потока записи.
					with open(f"{Directory}/{Filename}", "wb") as FileWriter:
						# Запись файла изображения.
						FileWriter.write(Response.content)
				
					# Если из ссылки не удалось определить тип файла.
					if FileType == "":
						# Определение типа при прмрщи библиотеки Pillow.
						Type = self.__DetermineImageType(f"{Directory}/{Filename}", ChapterID)
					
						# Если удалось определить тип.
						if Type: 
							# Переименование файла.
							os.rename(f"{Directory}/{Filename}", f"{Directory}/{Filename}.{Type}")
							# Обновление имени файла.
							Filename = f"{Filename}.{Type}"

					# Запись в лог сообщения: иллюстрация загружена.
					logging.info(f"Novel: {self.__ID}. Chapter: {ChapterID}. Image downloaded: \"{Filename}\".")
		
				else:
					# Запись в лог ошибки: не удалось скачать иллюстрацию.
					logging.error(f"Novel: {self.__ID}. Chapter: {ChapterID}. Unable to download image: \"{Link}\". Response code: {Response.status_code}.")
				
			except:
				# Запись в лог ошибки: не удалось скачать иллюстрацию из-за некорректной ссылки.
				logging.error(f"Novel: {self.__ID}. Chapter: {ChapterID}. Incorrect link to image.")
				
		else:
			# Добавление расширения к имени файла.
			Filename += FileType
			# Запись в лог сообщения: иллюстрация уже загружена.
			logging.info(f"Novel: {self.__ID}. Chapter: {ChapterID}. Image already exists: \"{Filename}\".")
			
		return Filename
	
	def __FilterStringData(self, Data: str):
		# Для каждого регулярного выражения удалить все вхождения.
		for Regex in self.__Filters: Data = re.sub(Regex, "", Data)

		return Data

	def __GetChapterName(self, ChapterName: str, Number: int | float | None) -> str | None:
		# Приведение номера главы к строке.
		Number = str(Number)
		
		# Если номер определён.
		if Number != "None":
			# Удаление символов до номера главы.
			Buffer = ChapterName.split(Number)
			Buffer.pop(0)
			Buffer = Number.join(Buffer)
			Buffer = re.sub("глава|часть|эпизод", "", Buffer, flags = re.IGNORECASE)
			Buffer = Buffer.lstrip("—.– ,:-")
			Buffer = Buffer.rstrip(" ")
			Buffer = RemoveRecurringSubstrings(Buffer, " ")
			ChapterName = Buffer
			# Если название главы пустое, обнулить его.
			if ChapterName == "": ChapterName = None

		# Если включена очистка названия и название имеется.
		if self.__Settings["prettifier"] and ChapterName != None:
			# Замена трёх точек символом многоточия.
			ChapterName.replace("...", "…")
			# Удаление повторяющихся символов многоточия.
			ChapterName = RemoveRecurringSubstrings(ChapterName, "…")
			# Удаление краевых символов.
			ChapterName = ChapterName.strip(".")

		# Если название имеется и не содержит букв.
		if ChapterName != None and IsNotAlpha(ChapterName): ChapterName = None
			
		return ChapterName
	
	def __GetNumberFromString(self, String: str) -> int | float | None:
		# Поиск первого числа.
		Result = re.search("\d+(\.\d+)?", String)
		# Число.
		Number = None
		
		# Если удалось найти число.
		if Result:
			# Получение строки.
			Result = Result[0]
			
			# Если число содержит точку.
			if "." in Result:
				# Преобразовать в число с плавающей запятой.
				Number = float(Result)
				
			else:
				# Преобразовать в число.
				Number = int(Result)

		return Number
	
	def __Merge(self):
		# Чтение локального файла.
		Local = ReadJSON(self.__Settings["novels-directory"] + f"/{self.__ID}.json")
		# Локальные определения глав.
		LocalChapters = dict()
		# Количество дополненных глав.
		MergedChaptersCount = 0
		
		# Для каждой главы.
		for Chapter in Local["chapters"][str(self.__ID)]:
			# Запись информации об абзацах.
			LocalChapters[Chapter["id"]] = Chapter["paragraphs"]
			
		# Для каждой главы.
		for ChapterIndex in range(0, len(self.__Novel["chapters"][str(self.__ID)])):
					
			# Если для главы с таким ID найдены абзацы.
			if self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["id"] in LocalChapters.keys():
				# Запись информации об абзацах.
				self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["paragraphs"] = LocalChapters[self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["id"]]
				# Инкремент количества дополненных глав.
				MergedChaptersCount += 1
						
		# Запись в лог сообщения: количество дополненных глав.
		logging.info(f"Novel: {self.__ID}. Merged chapters: {MergedChaptersCount}.")

	def __ReadFilters(self) -> list[str]:
		# Список регулярных выражений.
		RegexList = list()

		# Если файл фильтров существует.
		if os.path.exists("Filters.txt"):

			# Чтение содржимого файла.
			with open("Filters.txt", "r") as FileReader:
				# Буфер чтения.
				Bufer = FileReader.read().split("\n")
				
				# Для каждой строки.
				for String in Bufer:
					# Если строка не пуста и не комментарий, поместить её в список регулярных выражений.
					if String.strip() != "" and not String.startswith("#"): RegexList.append(String.strip())

		return RegexList

	#==========================================================================================#
	# >>>>> МЕТОДЫ ПАРСИНГА <<<<< #
	#==========================================================================================#
	
	def __Amend(self):
		# Количество дополненных глав.
		AmendedChaptersCount = 0 
				
		# Для каждой главы.
		for ChapterIndex in range(len(self.__Novel["chapters"][str(self.__ID)])):
			# Очистка консоли.
			Cls()
			# Вывод в консоль: сообщение из внешнего обработчика и прогресс.
			print(self.__Message + "\n" + f"Amending: " + str(ChapterIndex + 1) + " / " + str(len(self.__Novel["chapters"][str(self.__ID)])))
			
			# Если глава не имеет абзацев и не является платной.
			if self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["paragraphs"] == [] and not self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["is-paid"]:
				# ID главы.
				ID = self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["id"]
				# Запрос главы.
				Response = self.__Requestor.get(f"https://tl.rulate.ru/book/{self.__ID}/{ID}/ready_new")
			
				# Если запрос успешен.
				if Response.status_code == 200:
					# Парсинг страницы главы.
					Soup = BeautifulSoup(Response.text, "lxml")
					# Поиск контейнера глав.
					Container = Soup.find("div", {"class": "content-text"})
				
					# Если есть перевод.
					if Container != None:
						# Поиск всех вложенных тегов.
						Paragraphs = Container.find_all(["div", "p", "table", "blockquote"], recursive = False)
						# Буфер абзацев.
						Buffer = list()
				
						# Для каждого абзаца.
						for Paragraph in Paragraphs:
							
							# Для каждого тега p.
							for p in Paragraph.find_all("p"):
								# Если тег не содержит текста, удалить его.
								if p.get_text().strip() == "": p.decompose()
								
							# Код параграфа.
							ParagraphHTML = HTML(str(Paragraph))
							# Стиль выравнивания.
							Align = ""
							
							# Если абзац не содержит таблиц и цитаты.
							if "<table" not in ParagraphHTML.text and "<blockquote" not in ParagraphHTML.text:
								# Удаление тегов p.
								ParagraphHTML.remove_tags(["p"])
								# Поиск стиля.
								AlignStyle = re.search("text-align:.+;", str(ParagraphHTML.text))
								# Если тег имеет стиль выравнивания, оставить только его.
								if AlignStyle: Align = AlignStyle[0]
								
							# Обработка тегов.
							ParagraphHTML.remove_tags(["div"])
							ParagraphHTML.remove_tags(["ol", "li", "ul", "br", "span"])
							ParagraphHTML.replace_tag("em", "i")
							ParagraphHTML.replace_tag("strong", "b")
							# Получение текста для проверок.
							Text = ParagraphHTML.text.strip().replace("\xa0", " ")

							# Если включены фильтры.
							if self.__Settings["filters"]:

								# Для каждого абзаца провести фильтрацию.
								for Index in range(len(Buffer)): Buffer[Index] = self.__FilterStringData(Buffer[Index])

							# Если параграф не пустой и не является ссылкой, добавить его.
							if Text != "" and not self.__CheckForLinkParagraph(Text): Buffer.append(f"<p{Align}>{Text}</p>")
					
						# Индекс изображения.
						ImageIndex = 0
						
						# Для каждого абзаца обработать иллюстрации.
						for Index in range(len(Buffer)):
							# Парсинг абзаца.
							SmallSoup = BeautifulSoup(Buffer[Index], "html.parser")
							
							# Для каждого изображения.
							for Image in SmallSoup.find_all("img"):
								# Инкремент индекса изображения.
								ImageIndex += 1
								# Скачивание иллюстрации.
								Result = self.__DownloadImage(Image["src"], ID, ImageIndex)
								# Определение точки монтирования ссылок.
								ImagesDirectory = "/" + self.__Settings["images-directory"].split("/")[-1] if self.__Settings["link-to-images-directory"] else ""
								# Замена ссылки изображения.
								Image.attrs = {"src": ImagesDirectory + f"/{self.__ID}/{ID}/{Result}"}
								# Замена абзаца обработанным.
								Buffer[Index] = str(SmallSoup)
							
						# Для каждого абзаца обработать таблицы.
						for Index in range(len(Buffer)):
							# Парсинг абзаца.
							SmallSoup = BeautifulSoup(Buffer[Index], "html.parser")
							
							# Для каждого тега table.
							for table in SmallSoup.find_all("table"):
								# Удаление атрибутов.
								table.attrs = {}
								# Замена абзаца обработанным.
								Buffer[Index] = str(SmallSoup)
								
								# Для каждого тега p в таблице.
								for p in table.find_all("p"):
									
									# Если тег абзаца пустой.
									if p.get_text().strip() == "":
										# Удаление тега.
										p.decompose()
										
									else:
										# Поиск стиля.
										Align = re.search("text-align:.+;", str(p))
										# Если тег имеет стиль выравнивания, оставить только его.
										if Align: p["style"] = Align[0]
								
							# Для каждого тега td.
							for td in SmallSoup.find_all("td"):
								# Удаление атрибутов.
								td.attrs = {}
								# Замена абзаца обработанным.
								Buffer[Index] = str(SmallSoup)
								
						# Если включен форматировщик.
						if self.__Settings["prettifier"]:
							
							# Пока в последнем абзаце отсутсвуют буквенные символы, удалять последний абзац.
							while len(Buffer) > 0 and not re.search("[a-zA-ZА-я_]{3,}", Buffer[-1]): Buffer.pop()
							# Если в первом абзаце присутствует номер главы, удалить его.
							if len(Buffer) > 0 and re.search("глава \d+", Buffer[0], re.IGNORECASE) or len(Buffer) > 0 and re.search("^эпилог|пролог|экстра", Buffer[0], re.IGNORECASE): Buffer.pop(0)

						# Запись в лог сообщения: глава дополнена контентом.
						logging.info(f"Novel: {self.__ID}. Chapter: {ID}. Amended.")
						# Инкремент количества дополненных глав.
						AmendedChaptersCount += 1

						# Сохранение контента.
						self.__Novel["chapters"][str(self.__ID)][ChapterIndex]["paragraphs"] = Buffer
					
					else:
						# Запись в лог предупреждения: глава не содержит перевод.
						logging.warning(f"Novel: {self.__ID}. Chapter: {ID}. No translation.")
				
				else:
					# Запись в лог ошибки: не удалось получить содержимое главы.
					logging.error(f"Novel: {self.__ID}. Chapter: {ID}. Unable to load content.")
					
				# Выжидание интервала.
				sleep(self.__Settings["delay"])
				
		# Запись в лог сообщения: количество дополненных глав.
		logging.info(f"Novel: {self.__ID}. Chapters amended: {AmendedChaptersCount}.")
	
	def __CheckAgeLimit(self, Soup: BeautifulSoup) -> int:
		# Возрастной лимит.
		Limit = 0
		# Если найдена иконка возрастного ограничения, задать лимит в 18 лет.
		if Soup.find("span", {"class": "adult-icon"}): Limit = 18
		
		return Limit
	
	def __GetAuthor(self, Soup: BeautifulSoup) -> str | None:
		# Поиск контейнера с данными.
		DataContainer = Soup.find("div", {"class": "span5"})
		# Поиск всех абзацев с данными.
		DataBlocks = DataContainer.find_all("p")
		# Автор.
		Author = None
		
		# Для каждого блока.
		for Block in DataBlocks: 
			# Если блок содержит ник автора, записать его.
			if "Автор:" in str(Block): Author = Block.get_text().replace("Автор:", "").strip()
			
		return Author	
	
	def __GetCovers(self, Soup: BeautifulSoup) -> list:
		CoversContainer = Soup.find("div", {"class": "images"})
		CoversBlocks = CoversContainer.find_all("img")
		Covers = list()
		
		for Block in CoversBlocks:
			Buffer = {
				"link": "https://tl.rulate.ru" + Block["src"],
				"filename": Block["src"].split("/")[-1],
				"width": None,
				"height": None
			}
			Covers.append(Buffer)
			
		return Covers
	
	def __GetChapters(self, Soup: BeautifulSoup) -> list[dict]:
		# Поиск таблицы с главами.
		Table = Soup.find("table", {"id": "Chapters"}).find("tbody")
		# Поиск всех строк таблицы.
		Rows = Table.find_all("tr")
		# Текущий том.
		CurrentVolume = None
		# Список глав.
		Chapters = list()
		
		# Для каждой строки.
		for Row in Rows:
			
			# Если строка описывает том.
			if "volume_helper" in Row["class"] and Row.has_attr("id"):
				# Получение номера тома.
				CurrentVolume = self.__GetNumberFromString(Row.get_text())
				
			# Если строка описывает главу.
			if Row.has_attr("data-id"):
				# Поиск ссылок на главу.
				Links = Row.find_all("a")
				# Парсинг данных главы.
				ID = int(Row["data-id"])
				Number = self.__GetNumberFromString(Links[0].get_text())
				Name = self.__GetChapterName(Links[0].get_text(), Number)
				IsPaid = False if len(Links) > 1 else True
				# Буфер главы.
				Buffer = {
					"id": ID,
					"volume": CurrentVolume,
					"number": Number,
					"name": Name,
					"is-paid": IsPaid,
					"translator": None,
					"paragraphs": []
				}
				# Запись буфера.
				Chapters.append(Buffer)
				
		# Запись количества глав.
		self.__Novel["branches"][0]["chapters-count"] = len(Chapters)
		
		return Chapters
	
	def __GetDescription(self, Soup: BeautifulSoup) -> str | None:
		# Поиск блока описания.
		DescriptionBlock = Soup.find("div", {"style": "margin: 20px 0 0 0"})
		# Описание.
		Description = None
		
		# Если блок описания найден.
		if DescriptionBlock:
			# Поиск всех абзацев.
			Paragraphs = DescriptionBlock.find_all("p")
			# Приведение описания к строковому типу.
			Description = ""
			
			# Для каждого абзаца добавить строку описания.
			for p in Paragraphs: Description += HTML(p.get_text()).plain_text.strip() + "\n"
				
		# Удаление повторяющихся и концевых символов новой строки.
		Description = RemoveRecurringSubstrings(Description, "\n")
		Description = Description.strip("\n")
		# Если включены фильтры, обработать описание.
		if self.__Settings["filters"]: Description = self.__FilterStringData(Description)
		
		return Description

	def __GetOriginalLanguage(self, Soup: BeautifulSoup) -> str | None:
		# Определения кодов языков по стандарту ISO 639-1.
		LanguagesDeterminations = {
			"Китайские": "ZH",
			"Корейские": "KO",
			"Японские": "JA",
			"Английские": "EN",
			"Авторские": "RU",
			"Авторские фанфики": "RU",
			"Вьетнамские": "VI"
		}
		# Поиск кнопки смены категории.
		Action = Soup.find("a", {"class": "act"})
		# Если обнаружена кнопка смены категории, удалить её.
		if Action: Action.decompose()
		# Получение конечной категории новеллы.
		Category = Soup.find("p", {"class": "cat"}).find_all("a")[-1].get_text()
		# Оригинальный язык.
		Language = None
		# Если для категории определён язык, запомнить его код.
		if Category in LanguagesDeterminations.keys(): Language = LanguagesDeterminations[Category]

		return Language

	def __GetNovel(self) -> bool:
		# Состояние: успешен ли запрос.
		IsSuccess = False
		# Выполнение запроса.
		Response = self.__Requestor.get(f"https://tl.rulate.ru/book/{self.__ID}")
		
		# Если запрос успешен.
		if Response.status_code == 200:
			# Парсинг кода страницы.
			Soup = BeautifulSoup(Response.text, "html.parser")
			# Парсинг названий.
			Names = self.__GetNames(Soup)
			# Заполнение данных новеллы.
			self.__Novel["covers"] = self.__GetCovers(Soup)
			self.__Novel["ru-name"] = Names["ru"]
			self.__Novel["en-name"] = Names["en"]
			self.__Novel["another-names"] = Names["another"]
			self.__Novel["author"] = self.__GetAuthor(Soup)
			self.__Novel["publication-year"] = self.__GetPublicationYear(Soup)
			self.__Novel["age-rating"] = self.__CheckAgeLimit(Soup)
			self.__Novel["description"] = self.__GetDescription(Soup)
			self.__Novel["original-language"] = self.__GetOriginalLanguage(Soup)
			self.__Novel["status"] = self.__GetStatus(Soup)
			self.__Novel["series"] = self.__GetSeries(Soup)
			self.__Novel["genres"] = self.__GetTags("Жанры", Soup)
			self.__Novel["tags"] = self.__GetTags("Тэги", Soup)
			self.__Novel["chapters"][str(self.__ID)] = self.__GetChapters(Soup)
			# Переключение состояния.
			IsSuccess = True
			
		return IsSuccess
	
	def __GetNames(self, Soup: BeautifulSoup) -> dict:
		# Словарь названий.
		Names = {
			"ru": None,
			"en": None,
			"another": []
		}
		# Поиск названий.
		Title = Soup.find("h1").get_text()
		TitleParts = Title.split(" / ")
		# Английский словарь.
		EnglishDictionary = enchant.Dict("en_US")
		
		# Для каждой части названия.
		for Part in TitleParts:
			
			# Если название содержит кирилические символы.
			if CheckForCyrillicPresence(Part):
				
				# Если русское название не определено.
				if Names["ru"] == None:
					# Запись в главное русское название.
					Names["ru"] = Part
				
				else:
					# Запись в другие названия.
					Names["another"].append(Part)
				
			else:
				# Список слов в названии длинной более 2-ух символов.
				Words = list()
				# Количество слов, найденных в английском словаре.
				EnglishWordsCount = 0

				# Для каждого слова.
				for Word in Part.split(' '):
					
					# Если слово длиннее 2-ух символов, записать его.
					if len(Word) > 2: Words.append(Word)
					
				# Для каждого слова.
				for Word in Words:
						
					# Если слово есть в английском словаре, выполнить инкремент.
					if EnglishDictionary.check(Word) == True: EnglishWordsCount += 1
				
				# Если больше трети слов английские.
				if EnglishWordsCount >= int(len(Words) / 3):
						
					# Если английское название не определено.
					if Names["en"] == None:
						# Запись в главное английское название.
						Names["en"] = Part
				
					else:
						# Запись в другие названия.
						Names["another"].append(Part)
							
				else:
					# Запись в другие названия.
					Names["another"].append(Part)
		
		# Поиск контейнера с данными.
		DataContainer = Soup.find("div", {"class": "span5"})
		# Поиск всех тегов абзаца.
		DataBlocks = DataContainer.find_all("p")
		
		# Для каждого тега.
		for Block in DataBlocks: 
			
			# Если тег содержит альтернативное название.
			if "Альтернативное название:" in str(Block):
				# Запись альтернативного названия.
				Names["another"].append(Block.get_text().replace("Альтернативное название:", "").strip())

		return Names
	
	def __GetPublicationYear(self, Soup: BeautifulSoup) -> int | None:
		DataContainer = Soup.find("div", {"class": "span5"})
		DataBlocks = DataContainer.find_all("p")
		Year = None
		
		for Block in DataBlocks: 
			
			if "Год выпуска:" in str(Block):
				Year = int(Block.get_text().replace("Год выпуска:", "").strip())
			
		return Year
	
	def __GetSeries(self, Soup: BeautifulSoup) -> str | None:
		# Поиск контейнера с данными.
		DataContainer = Soup.find("div", {"class": "span5"})
		# Поиск всех абзацев с данными.
		DataBlocks = DataContainer.find_all("p")
		# Список серий.
		Series = list()
		
		# Для каждого блока.
		for Block in DataBlocks: 
			
			# Если блок содержит названия серий автора.
			if "Фэндом:" in str(Block):
				# Парсинг блока серий.
				SmallSoup = BeautifulSoup(str(Block), "html.parser")
				# Поиск ссылок на фэндомы.
				FandomsLinks = SmallSoup.find_all("a")
				# Для каждой ссылки записать название серии.
				for Link in FandomsLinks: Series.append(Link.get_text())
			
		return Series	
	
	def __GetStatus(self, Soup: BeautifulSoup) -> str:
		# Определения статусов.
		Statuses = {
			"В работе": "ONGOING",
			"Перерыв": "ABANDONED",
			"Ожидание новых глав": "ABANDONED",
			"Завершён": "COMPLETED"
		}
		# Статус.
		Status = "UNKNOWN"
		# Поиск строки статуса.
		StatusLine = Soup.find_all("dl", {"class": "info"})[1].find("dd").get_text().split("(")[0].strip()
		# Если строка статуса определена, установить статус.
		if StatusLine in Statuses.keys(): Status = Statuses[StatusLine]
			
		return Status
	
	def __GetTags(self, Type: str, Soup: BeautifulSoup) -> list:
		DataContainer = Soup.find("div", {"class": "span5"})
		DataBlocks = DataContainer.find_all("p")
		Genres = list()
		
		for Block in DataBlocks: 
			
			if Type + ":" in str(Block):
				GenresBlocks = Block.find_all("a")
				
				for Genre in GenresBlocks:
					Genres.append(Genre.get_text().strip().lower())
			
		return Genres	

	def __init__(self, Settings: dict, Requestor: WebRequestor, ID: int | str, ForceMode: bool = True, Message: str = ""):
		
		#---> Генерация динамических свойств.
		#==========================================================================================#
		# Список фильтров на основе регулярных выражений.
		self.__Filters = self.__ReadFilters()
		# Глоабльные настройки.
		self.__Settings = Settings
		# Менеджер запросов.
		self.__Requestor = Requestor
		# ID новеллы.
		self.__ID = int(ID)
		# Состояние: включён ли режим перезаписи.
		self.__ForceMode = ForceMode
		# Сообщение из внешних обработчиков.
		self.__Message = Message + "Current novel: " + ID + "\n"
		# Структура новеллы.
		self.__Novel = {
			"format": "dnp-v1",
			"site": "tl.rulate.ru",
			"id": self.__ID,
			"slug": str(self.__ID),
			"covers": [],
			"ru-name": None,
			"en-name": None,
			"another-names": [],
			"author": None,
			"publication-year": None,
			"age-rating": None,
			"description": None,
			"original-language": None,
			"status": None,
			"is-licensed": False,
			"series": [],
			"genres": [],
			"tags": [],
			"branches": [
				{
					"id": self.__ID,
					"chapters-count": 0
				}
			],
			"chapters": {
				str(self.__ID): []
			}
		}
		# Состояние: доступна ли новелла для парсинга.
		self.__IsAccesed = None
		
		#---> Подготовка к парсингу.
		#==========================================================================================#
		# Очистка консоли.
		Cls()
		# Вывод в консоль: базовое сообщение.
		print(self.__Message)
		# Запись в лог сообщения: старт парсинга.
		logging.info(f"Novel: {self.__ID}. Parsing...")
		
		#---> Получение данных о новелле.
		#==========================================================================================#
		# Парсинг страницы новеллы.
		self.__IsAccesed = self.__GetNovel()
		
		# Если удалось спарсить страницу новеллы.
		if self.__IsAccesed:
			
			# Если уже существует описательный файл и режим перезаписи отключен.
			if os.path.exists(self.__Settings["novels-directory"] + f"/{ID}.json") and not ForceMode:
				# Запись в лог сообщения: информация будет перезаписана.
				logging.info(f"Novel: {self.__ID}. Local JSON already exists. Merging...")
				# Слияние источников.
				self.__Merge()
				
			# Если уже существует описательный файл и режим перезаписи включен.
			elif os.path.exists(self.__Settings["novels-directory"] + f"/{ID}.json") and ForceMode:
				# Запись в лог сообщения: информация будет перезаписана.
				logging.info(f"Novel: {self.__ID}. Local JSON already exists. Will be overwritten...")

			# Дополнение глав.
			self.__Amend()
		
		else:
			# Запись в лог предупреждения: новелла недоступна.
			logging.warning(f"Novel: {self.__ID}. Not accesed. Skipped.")
		
	def download_covers(self):
		# Количество загруженных обложек.
		DownloadedCoversCount = 0
		# Очистка консоли.
		Cls()
		# Вывод в консоль: заголовок парсинга.
		print(self.__Message)
		
		# Для каждой обложки.
		for Cover in self.__Novel["covers"]:
			# Вывод в консоль: загрузка обложки.
			print("Downloading cover: \"" + Cover["link"] + "\"... ", end = "")
			# Директория загрузки.
			Directory = self.__Settings["covers-directory"] + f"/{self.__ID}"
			# Если директория не существует, создать.
			if not os.path.exists(Directory): os.makedirs(Directory)
			# Имя файла.
			Filename = Cover["link"].split("/")[-1].split("?")[0]
			# Состояние: существует ли уже обложка.
			IsAlreadyExists = os.path.exists(f"{Directory}/{Filename}")
			
			# Если обложка не загружена или загружена, но включен режим перезаписи.
			if not IsAlreadyExists or IsAlreadyExists and self.__ForceMode:
				# Выполнение запроса.
				Response = requests.get(Cover["link"])
		
				# Если запрос успешен.
				if Response.status_code == 200:

					# Открытие потока записи.
					with open(f"{Directory}/{Filename}", "wb") as FileWriter:
						# Запись файла изображения.
						FileWriter.write(Response.content)
					
					# Инкремент количества загруженных обложек.
					DownloadedCoversCount += 1
					# Вывод в консоль: загрузка завершена.
					print("Done.")
				
				else:
					# Вывод в консоль: ошибка загрузки.
					print("Failure!")
				
				# Выжидание интервала.
				sleep(self.__Settings["delay"])
				
			else:
				# Вывод в консоль: обложка уже существует.
				print("Already exists.")
					
		# Запись в лог сообщения: старт парсинга.
		logging.info(f"Novel: {self.__ID}. Covers downloaded: {DownloadedCoversCount}.")

	def save(self):
		# Если каталог для новелл не существует, создать.
		if os.path.exists(self.__Settings["novels-directory"]) == False: os.makedirs(self.__Settings["novels-directory"])
		# Запись файла.
		WriteJSON(self.__Settings["novels-directory"] + f"/{self.__ID}.json", self.__Novel)