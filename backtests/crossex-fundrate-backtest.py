# coding=utf-8
import asyncio
import aiohttp
import json
from datetime import datetime
import dateutil.parser
import time
import csv
import codecs
import math
base_url = "https://api.binance.com/api/v3/"
base_url_fapi = "https://fapi.binance.com"
kline_req_url = base_url+"klines"
fundrate_req_url = base_url_fapi+"/fapi/v1/fundingRate"

base_url_huo = "https://api.hbdm.com"
fundrate_req_url_huo = "/linear-swap-api/v1/swap_historical_funding_rate"

base_url_ok = "https://aws.okex.com"
fundrate_req_url_ok = "/api/swap/v3/instruments/" #"/historical_funding_rate"



itv='8h'

# 初始本金
initfund = 100000


async def request(session,url):
    headers = {'content-type': 'application/json'}
    async with session.get(url,headers=headers) as res:
        return await res.text()

async def fetch_instruments_binance():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        fundrate_url = base_url_fapi+'/fapi/v1/exchangeInfo'
        #print(fundrate_url )
        retr = await request(session,fundrate_url)
        arrobj_r = json.loads(retr)
        retarr = {}
        for symb in arrobj_r['symbols']:
            if(symb['contractType'] == 'PERPETUAL'):
                retarr[symb['baseAsset']] = (symb['symbol'])
        return retarr
        
async def fetch_instruments_huobi():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        fundrate_url = base_url_huo+'/linear-swap-api/v1/swap_open_interest'
        #print(fundrate_url )
        retr = await request(session,fundrate_url)
        retarr = {}
        arrobj_r = json.loads(retr)
        for symb in arrobj_r['data']:
            retarr[symb['symbol']] = symb['contract_code']
        return retarr

async def fetch_instruments_okex():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        fundrate_url = base_url_ok+'/api/swap/v3/instruments'
        #print(fundrate_url )
        retr = await request(session,fundrate_url)
        retarr = {}
        arrobj_r = json.loads(retr)
        for symb in arrobj_r:
            retarr[symb['underlying_index']] = symb['instrument_id']
        return retarr


async def fetch_binance_rate_history(symbols,alltime,starttimef):
    bSymbRTimeseries = {}
    seriestimecol = []
    for symb in symbols:
        timeratedict = {}
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            now = datetime.now()
            startTime = 1483228800000 # 2017/1/1
            t = startTime
            endTime = int(time.mktime(now.timetuple())*1e3)
            
            while(t <= endTime):
                fundrate_url = fundrate_req_url +'?symbol='+ symbols[symb] +'&startTime='+str(t)+'&limit=1000'
                #print(fundrate_url )
                retr = await request(session,fundrate_url)
                arrobj_r = json.loads(retr)
                
                for fds in arrobj_r:
                    ktime = int(fds['fundingTime']/1000)
                    if(not ktime  in timeratedict):
                        fundrate = float(fds['fundingRate'])
                        timeratedict[ktime] = fundrate
                        if(not ktime in alltime): #
                            alltime.append(ktime)
                            print('binance',ktime)
                    if(not ktime  in timeratedict):
                        seriestimecol.append(ktime)
                    
                    if(not ktime  in seriestimecol):
                        seriestimecol.append(ktime)                    
                if(len(arrobj_r)<1):
                    break
                t = arrobj_r[len(arrobj_r)-1]['fundingTime']+1000 # 拿最後一筆資料的收盘时间當作下一個的開頭
        bSymbRTimeseries[symb] = timeratedict
    seriestimecol.sort()
    seriesstart = seriestimecol[0]
    if(seriesstart>starttimef):starttimef = seriesstart
    return bSymbRTimeseries,starttimef

async def fetch_huobi_rate_history(symbols,alltime,starttimef):
    hSymbRTimeseries = {}
    seriestimecol = []
    for symb in symbols:
        timeratedict = {}
        totalpage = 0
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            fundrate_url = base_url_huo + fundrate_req_url_huo +'?contract_code='+ symbols[symb]
            retr = await request(session,fundrate_url)
            arrobj_r = json.loads(retr)
            totalpage = arrobj_r['data']['total_page']
            if(totalpage>0):
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session2:
                    fundrate_url_t = base_url_huo + fundrate_req_url_huo +'?contract_code='+ symbols[symb]+'&page_size='+str(totalpage)
                    print(fundrate_url_t)
                    retr2 = await request(session2,fundrate_url_t)
                    arrobj_r2 = json.loads(retr2)
                    
                    for fds in arrobj_r2['data']['data']:
                        ktime = int(int(fds['funding_time'])/1000)
                        if(not ktime  in timeratedict):
                            fundrate = float(fds['realized_rate'])
                            timeratedict[ktime] = fundrate
                            if(not ktime in alltime): #
                                alltime.append(ktime)
                            else:                                
                                print('huobi has funding time',ktime)
                        
                        if(not ktime  in seriestimecol):
                            seriestimecol.append(ktime)
                        if(len(arrobj_r)<1):
                            break
            
        hSymbRTimeseries[symb] = timeratedict
    seriestimecol.sort()
    seriesstart = seriestimecol[0]
    if(seriesstart>starttimef):starttimef = seriesstart
    return hSymbRTimeseries,starttimef

async def fetch_okex_rate_history(symbols,alltime,starttimef):
    hSymbRTimeseries = {}
    startfime = 0
    seriestimecol = []   
    for symb in symbols:
        timeratedict = {}
        totalpage = 0
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            fundrate_url = base_url_ok + fundrate_req_url_ok + symbols[symb] +"/historical_funding_rate"
            print(fundrate_url)
            retr = await request(session,fundrate_url)
            arrobj_r = json.loads(retr)
            
            for fds in arrobj_r:
                ktime = int(time.mktime(dateutil.parser.parse(fds['funding_time']).timetuple()))
                if(startfime <1):startfime = ktime
                if(not ktime  in timeratedict):
                    fundrate = float(fds['realized_rate'])
                    timeratedict[ktime] = fundrate
                    if(not ktime in alltime): #
                        alltime.append(ktime)
                    else:
                        print('okex has funding time',ktime)
                if(not ktime  in seriestimecol):
                    seriestimecol.append(ktime)
                
            if(len(arrobj_r)<1):
                break
            
        hSymbRTimeseries[symb] = timeratedict
    seriestimecol.sort()
    seriesstart = seriestimecol[0]
    if(seriesstart>starttimef):starttimef = seriesstart
    return hSymbRTimeseries,starttimef



def aggregate(alltime,bin_series,huo_series,ok_series,starttimef):
    # collect all timestamp
    retdict = {}
    
    compoundfund = initfund # 累計本金          
    positiveFundTimes = 0 # 勝率 資費為正的次數 
    totalFundTimes = 0  # 資費總次數
    
    
    # mdd
    hh = -9999
    dd = 9999
    mdd = 9999
    
    # 日內最大回撤
    prvdaynetprofit = -9999
    dmdd = 9999
    
    # 最長未創高區間
    lastHHTimestamp = 0
    longestHHPeriod = -9999
    
    
    # 波動率
    avgfundrate = 0
    prvcompfund = 0
    avgvolatility = 0
    fundratecoll = []
    
    timestart = 0
    
    def checkdif(ex1,ex2,ser1,ser2,name1,name2,feedif=-9999):
        avaliable1 = curtime in ser1[name1]
        avaliable2 = curtime in ser2[name2]
        if(avaliable1 and avaliable2):
            
            fee1 = ser1[name1][curtime]
            fee2 = ser2[name2][curtime]
            print(ex1,ex2,curtime,name1,fee1,fee2)
            negative = (fee1 * fee2) < 0
            if(negative):
                _feedif = abs(fee1)+abs(fee2)
                if(_feedif > feedif):
                    feedif = _feedif
        return feedif
    startIdx = alltime.index(starttimef)
    for k in range(startIdx,len(alltime)):
        curtime = alltime[k]
        feediff = -9999
        for coinA in bin_series:
            for coinB in huo_series:
                for coinC in ok_series:
                    if(coinA==coinB):
                        #print('now ',curtime,' check binance & huobi', coinA )
                        feediff = checkdif('binance','huobi',bin_series, huo_series,coinA,coinB,feediff)
                    if(coinB==coinC):
                        #print('now ',curtime,' check huobi & okex', coinC )
                        feediff = checkdif('huobi','okex',huo_series, ok_series,coinB,coinC,feediff)
                    if(coinC==coinA):
                        #print('now ',curtime,' check huobi & okex', coinA )
                        feediff = checkdif('okex','binance', ok_series, bin_series,coinC,coinA,feediff)
            
        if(not curtime  in retdict):
            if(feediff>0):
                if(timestart<1):timestart = curtime
                totalFundTimes += 1
                positiveFundTimes +=1            
                compoundfund += compoundfund*feediff
            
                retdict[curtime] = [feediff,compoundfund-initfund]
                fundratecoll.append(feediff)
                print(str(curtime) + ' fundrate:'+str(feediff)+' compoundfund:'+str(compoundfund))
                avgfundrate += feediff
                
            
            # 計算 d_dd 日內波動
            if((totalFundTimes%3)==0):
                #print('one day has passed , current time = '+ str(curtime))
                todaynetprofit = compoundfund*feediff
                d_dd = todaynetprofit-prvdaynetprofit
                if(d_dd < dmdd):dmdd = d_dd # d_dd
                prvdaynetprofit = todaynetprofit
            
            # 計算 mdd 創高區間
            if(compoundfund > hh):
                hh=compoundfund
                if(lastHHTimestamp<1):lastHHTimestamp=curtime
                period = (curtime - lastHHTimestamp)
                if(period > longestHHPeriod):
                    longestHHPeriod = period
                lastHHTimestamp = curtime
            elif(compoundfund < hh):
                dd = compoundfund - hh
                if(dd < mdd):mdd=dd
            
            # 波動累加 報酬率累加
            if(prvcompfund<1):prvcompfund = compoundfund
            avgvolatility += abs(compoundfund - prvcompfund) / prvcompfund
            
            prvcompfund = compoundfund
            
    # 計算績效
    avgfundrate /= totalFundTimes
    avgvolatility /= totalFundTimes
    winrate = (positiveFundTimes / totalFundTimes)*100
    
    # sharp
    def variance(data, ddof=0):
        n = len(data)
        mean = sum(data) / n
        return sum((x - mean) ** 2 for x in data) / (n - ddof)
    def stdev(data):
        var = variance(data)
        std_dev = math.sqrt(var)
        return std_dev            
    sharpe = avgfundrate / stdev(fundratecoll)
    
    
    retdict['fundstart'] = alltime[0]
    retdict['fundend'] = alltime[-1]
    
    retdict['positiveFundTimes'] = positiveFundTimes
    retdict['totalFundTimes'] = totalFundTimes # 盈利次數
    
    
    retdict['compoundfund'] = compoundfund  # 總報酬
    retdict['winrate'] = winrate # 勝率
    retdict['longestHHPeriod'] = longestHHPeriod/86400000 # 創高區間
    retdict['mdd'] = (mdd/initfund)*100 # mdd
    retdict['dmdd'] = (dmdd/initfund)*100 # dmdd
    retdict['sharpe'] = sharpe # sharpe
    retdict['avgvolatility'] = avgvolatility # avgvolatility
    
    
    return retdict
    
async def backtest():
    alltime = []
    binance_instruments = await fetch_instruments_binance()
    huobi_instruments = await fetch_instruments_huobi()
    okex_instruments = await fetch_instruments_okex()
    starttimef = 0
    binance_symb_rate_timeseries,starttimef = await fetch_binance_rate_history(binance_instruments,alltime,starttimef)
    huobi_symb_rate_timeseries,starttimef = await fetch_huobi_rate_history(huobi_instruments,alltime,starttimef)
    okex_symb_rate_timeseries,starttimef = await fetch_okex_rate_history(okex_instruments,alltime,starttimef)
    alltime.sort()
    fundhist = await aggregate(alltime,binance_symb_rate_timeseries,huobi_symb_rate_timeseries,okex_symb_rate_timeseries,starttimef)
    
    file_object = codecs.open('fundrate_report.txt', 'w', "utf-8")
    file_object.write('')
    file_object.close()
    
    for ins in instruments:
        starttime = fundhist[ins]['fundstart'] / 1000
        endtime = fundhist[ins]['fundend'] / 1000
        starttime_dt = datetime.fromtimestamp(starttime)
        endtime_dt = datetime.fromtimestamp(endtime)
        
        durationDays = (fundhist[ins]['fundend'] - fundhist[ins]['fundstart']) / 86400000
        onedayret = (fundhist[ins]['compoundfund'] - initfund)/durationDays/initfund
        yearret = onedayret * 365 * 100
        yearret_str = "{:.2f}".format(yearret)
        
        positiveRatio = (fundhist[ins]['positiveFundTimes'] / fundhist[ins]['totalFundTimes'])*100
        positiveRatio_str = "{:.2f}".format(positiveRatio)
        
        netReturn = fundhist[ins]['compoundfund'] - initfund
        netReturn_str = "{:.2f}".format(netReturn)
        grossRate = (netReturn / initfund)/durationDays*365*100
        grossRate_str = "{:.2f}".format(grossRate)
        
        msg = u''
        msg += ins + 'USDT \n'
        msg += u'回測時間:'+str(starttime_dt)+' to '+str(endtime_dt)+ ' 共 ' +str(int(durationDays)) + ' 天 \n'
        msg += u'初始資金:'+ str(initfund) +'USD\n'
        msg += u'費率為正次數:'+ str(fundhist[ins]['positiveFundTimes'])+'\n'
        msg += u'總領費率次數:'+ str(fundhist[ins]['totalFundTimes'])+'\n'
        msg += u'勝率:'+ positiveRatio_str +'%\n'
        msg += u'總利潤:'+ netReturn_str +'USD\n'
        msg += u'最大創高區間:'+ ("{:.2f}".format(fundhist[ins]['longestHHPeriod'])) +'天\n'
        msg += u'最大拉回:'+ ("{:.2f}".format(fundhist[ins]['mdd'])) +'%\n'
        msg += u'每日最大拉回:'+ ("{:.2f}".format(fundhist[ins]['dmdd'])) +'%\n'
        msg += u'夏普比率:'+ ("{:.2f}".format(fundhist[ins]['sharpe'])) +'\n'
        msg += u'波動率:'+ ("{:.2f}".format(fundhist[ins]['avgvolatility'])) +'%\n'
        msg += u'每月報酬:'+ ("{:.2f}".format(grossRate/12.0)) +'%\n'
        msg += u'年化報酬:'+ grossRate_str +'%\n\n'
        
        
        file_object = codecs.open('fundrate_report.txt', 'a', "utf-8")
        file_object.write(msg)
        file_object.close()        
        
        
        
        # 圖表資料
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            kline_url = kline_req_url+'?symbol='+ins+'USDT&interval='+itv+'&startTime='+str( fundhist[ins]['fundstart'] )+'&endTime='+str(fundhist[ins]['fundend'])+'&limit=1000'
            ret = await request(session,kline_url)
            arrobj = json.loads(ret)
            if(len(arrobj)<1):return
            
        
            # combine data
            timestampcol = []
            timeprice = {}
            for key in fundhist[ins]:
                if(type(key) != type(1)):continue
                timestampcol.append(key)
            for kline in arrobj:
                time = kline[0]
                if(not time in timeprice):
                    timeprice[time] = kline[4]
                timestampcol.append(time)
            
            # 
            timestampcol.sort()
            
            
            with open( (ins+'_price.csv'), mode='w') as fprice_file:
                fprice_file = csv.writer(fprice_file , delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                fprice_file.writerow(['time','fundrate','netprofit','price'])

                prvrate = 0
                prvnetprofit = 0
                prvprice = 0
                for tt in timestampcol:
                    if(tt in fundhist[ins]):
                        prvrate = fundhist[ins][tt][0] * 3 * 365 * 100
                        prvnetprofit = fundhist[ins][tt][1]
                    elif(tt in timeprice):
                        prvprice = timeprice[tt]
                    _dt = datetime.fromtimestamp(tt/1000)
                    fprice_file.writerow([_dt,prvrate,prvnetprofit,prvprice])
        
        
    
    
    
    
    
    
    
    
    # 綜合績效
    # 目前人工挑選，長遠來看具備上漲基本面及
    # 及歷史回測績效較好的幣種
    coinlist = ['ETH','EGLD','DOGE','DOT','LTC']
    coinweight = {'ETH':0.18,'EGLD':0.35,'DOGE':0.24,'DOT':0.1,'LTC':0.13}
    
    
    yearret = 0
    positiveRatio = 0
    mdd = 9999
    dmdd = 9999
    sharpe = 0
    avgvolatility = 0
    netReturn = 0
    grossRate = 0
    durationDays = 0
    starttime_dt = None
    endtime_dt = None
    timestart = 29207694050000
    timeend = -9999
    positiveFundTimes = 0
    totalFundTimes = 0
    for ins in coinlist:
        ndays = (fundhist[ins]['fundend'] - fundhist[ins]['fundstart']) / 86400000
        starttime = fundhist[ins]['fundstart']/1000
        endtime = fundhist[ins]['fundend']/1000
        if(ndays>durationDays):durationDays=ndays
        if(starttime < timestart):
            starttime_dt = datetime.fromtimestamp(starttime)
            timestart = starttime
        if( endtime > timeend):
            endtime_dt = datetime.fromtimestamp(endtime)
            timeend = endtime
        
        onedayret = (fundhist[ins]['compoundfund'] - initfund)/ndays/initfund
        yearret += onedayret * 365 * 100 * coinweight[ins]
        positiveFundTimes += fundhist[ins]['positiveFundTimes']
        totalFundTimes += fundhist[ins]['totalFundTimes']        
        positiveRatio += (fundhist[ins]['positiveFundTimes'] / fundhist[ins]['totalFundTimes']) * 100 * coinweight[ins]
        netReturn += (fundhist[ins]['compoundfund'] - initfund) * coinweight[ins]
        grossRate += ((netReturn / initfund)/ndays*365*100) * coinweight[ins]
        sharpe += fundhist[ins]['sharpe'] * coinweight[ins]
        avgvolatility += fundhist[ins]['avgvolatility'] * coinweight[ins]
        if(fundhist[ins]['mdd']<mdd ):mdd=fundhist[ins]['mdd']
        if(fundhist[ins]['dmdd']<dmdd ):dmdd=fundhist[ins]['dmdd']
    
    
    msg = u''
    msg += "'ETH','EGLD','DOGE','DOT','LTC' 綜合費率套利績效\n"
    msg += u'回測時間:'+str(starttime_dt)+' to '+str(endtime_dt)+ ' 共 ' +str(int(durationDays)) + ' 天 \n'
    msg += u'初始資金:'+ str(initfund) +'USD\n'
    msg += u'費率為正次數:'+ str(positiveFundTimes)+'\n'
    msg += u'總領費率次數:'+ str(totalFundTimes)+'\n'
    msg += u'勝率:'+  ("{:.2f}".format(positiveRatio)) +'%\n'
    msg += u'總利潤:'+ ("{:.2f}".format(netReturn)) +'USD\n'
    msg += u'最大拉回:'+ ("{:.2f}".format(mdd)) +'%\n'
    msg += u'每日最大拉回:'+ ("{:.2f}".format(dmdd)) +'%\n'
    msg += u'夏普比率:'+ ("{:.2f}".format(sharpe)) +'\n'
    msg += u'波動率:'+ ("{:.2f}".format(avgvolatility)) +'%\n'
    msg += u'每月報酬:'+ ("{:.2f}".format(grossRate/12.0)) +'%\n'
    msg += u'年化報酬:'+ ("{:.2f}".format(grossRate)) +'%\n\n'
    
    file_object = codecs.open('fundrate_backtest_combine.txt', 'w', "utf-8")
    file_object.write(msg)
    file_object.close()        
    
    timestampcol = []
    for ins in coinlist:
        for key in fundhist[ins]:
            if(type(key) != type(1)):continue
            timestampcol.append(key)
    
    timestampcol.sort() 
    with open( ('combine_return.csv'), mode='w') as fprice_file:
        fprice_file = csv.writer(fprice_file , lineterminator='\n', delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        fprice_file.writerow(['time','fundrate','netprofit'])

        prvrate = {}
        prvnetprofit = {}
        for tt in timestampcol:
            for ins in coinlist:
                if(tt in fundhist[ins]):
                    prvrate[ins] = (fundhist[ins][tt][0] * 3 * 365 * 100) * coinweight[ins]
                    prvnetprofit[ins] = (fundhist[ins][tt][1]) * coinweight[ins]
            
            def _sum(arr):
                sum=0
                for i in arr:
                    sum = sum + i
                return(sum)               
            rate = _sum( list(prvrate.values()) )
            netprofit = _sum( list(prvnetprofit.values()) )
            _dt = datetime.fromtimestamp(tt/1000)
            dtformat = _dt.strftime('%Y-%m-%d %H:%M:%S')
            fprice_file.writerow([dtformat,rate,netprofit])

    
    print('done')

if __name__ == "__main__":
    asyncio.run(backtest())
