# walmart
爬取沃尔玛网站指定产品的评论内容

#Usage: walmart [options]

#Options:
  -h --help                 Show this on screen.
  -v --version              Show version.
  -l --link=<link>          Product review page link
  -p --page=<page>          The number of pages that you want to scrap
  -t --translate            Translate title and content via Youdao API
  -f --filename=<filename>  Specify output file name

#Example:
  walmart -l https://www.walmart.com/reviews/product/47055697 -p 10 -t walmart.xlsx

#Remark:
  link can be multiple and just need to be separated with ';'
  e.g. walmart -l linka;linkb