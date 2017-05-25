# -*- encoding:utf-8 -*-



import sys

def inputFun(src):
    return input(src)
def printFun(src,mode=1,srcLen=None):
    if not src:
        return
    temp_len = len(src) if not srcLen else srcLen
    if mode ==1:
        print src.center(temp_len)
    elif mode == 2:
        print src.ljust(temp_len)
    else:
        print src.rjust(temp_len)


def get_goods_list():
    return {'房子': 500000, '车子': 120000, '手表': 3000, '笔记本': 6000, '自行车': 300};
def show_goods_list():
    goods_list = get_goods_list()
    for item in enumerate(goods_list,1):
        print item[0],item[1],goods_list[item[1]]
    print 0,'exit'
def get_min_goods_price():
    return min(get_goods_list().values())
def show_purchase_history(buyList):
    if len(buyList) > 0:
        printFun("以下是您的购物清单：")
        printFun("--------------")
        consume = 0
        for item in enumerate(buyList, 1):
            consume += buyList[item[1]]
            print item[0], item[1], buyList[item[1]]
        printFun("总计消费：{0}".format(consume))
        printFun("--------------")
        printFun("欢迎下次再来")
def exit_goods(purchase_history):
    show_purchase_history(purchase_history)
    printFun("seft logout")
    sys.exit(0)
if __name__ == '__main__':
    printFun("----------------------------")
    wages = inputFun("please input your wages")
    min_good_price = get_min_goods_price()
    temp_wages = wages
    purchase_history = {}
    while True:
        printFun("---------------------")
        if temp_wages < min_good_price:
            printFun("您的余额为：{0}，对不起，本店没有合适您的商品了！".format(temp_wages))
            exit_goods(purchase_history)
        else:
            printFun("您的余额为：{0}，请选择您需要的商品：".format(temp_wages))
            show_goods_list()
            number = inputFun("")
            if number == 0:
                exit_goods(purchase_history)
            else:
                goods_list = get_goods_list()
                for item in enumerate(goods_list, 1):
                    if (item[0] == number):
                        goods_price = goods_list[item[1]]
                        if (temp_wages >= goods_price):
                            printFun("您购买：{0}，成功。消费：{1}".format(item[1], goods_price))
                            # 已经购买个这个产品
                            if purchase_history.has_key(item[1]):
                                purchase_history[item[1]] += goods_price
                            else:
                                purchase_history[item[1]] = goods_price

                            temp_wages = temp_wages - goods_price
                            number = inputFun("是否继续购买商品(1/0)?:")
                            if number == 0:
                                exit_goods(purchase_history)
                        else:
                            printFun("您购买：{0}，失败，您的余额不足，要不换个便宜的商品。".format(item[1]))
else:
    printFun("非法使用")           	