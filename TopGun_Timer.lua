-- =========================================================
-- TOP GUN: MAVERICK - TIMER MODULE (峽谷計時器)
-- =========================================================

env.info("LOADING TOPGUN TIMER MODULE")

if not TOPGUN_MISSION then
    env.error("TOPGUN TIMER MODULE FAILED: Core module not loaded!")
    return
end

-- 常數設定
TOPGUN_MISSION.INGRESS_ZONE_NAME = "Ingress_Zone"

local IngressZone = ZONE:FindByName(TOPGUN_MISSION.INGRESS_ZONE_NAME)
if not IngressZone then
    env.warning(TOPGUN_MISSION.INGRESS_ZONE_NAME .. " not found! Timer will not start automatically.")
end

local PlayersSet = SET_CLIENT:New():FilterCoalitions("blue"):FilterActive():FilterStart()

local TimerActive = false
local StartTime = 0
local ElapsedTime = 0

-- 觸發計時開始的函數 (可由外部腳本或事件呼叫)
function TOPGUN_MISSION.StartTimer()
    if not TimerActive then
        TimerActive = true
        StartTime = timer.getTime()
        MESSAGE:New("CLOCK IS RUNNING! Go! Go! Go!", 5, "MISSION"):ToAll()
        TOPGUN_MISSION.TriggerEvent("OnTimerStarted")
    end
end

-- 觸發計時停止的函數
function TOPGUN_MISSION.StopTimer()
    if TimerActive then
        TimerActive = false
        local FinalTime = timer.getTime() - StartTime
        local mins = math.floor(FinalTime / 60)
        local secs = math.floor(FinalTime % 60)
        local Msg = string.format("TARGET HIT! Final Time: %02d:%02d", mins, secs)
        MESSAGE:New(Msg, 15, "MISSION"):ToAll()
        TOPGUN_MISSION.TriggerEvent("OnTimerStopped", FinalTime)
    end
end

-- 監控玩家是否進入峽谷起點區域
local function CheckIngress()
    if TimerActive then return end
    
    PlayersSet:ForEachClient(function(Client)
        if not Client:IsAlive() then return end
        local PlayerCoord = Client:GetCoordinate()
        if PlayerCoord and IngressZone and IngressZone:IsCoordinateInZone(PlayerCoord) then
            TOPGUN_MISSION.StartTimer()
        end
    end)
end

-- 每秒更新一次畫面上的碼表
local function UpdateUI()
    if TimerActive then
        ElapsedTime = timer.getTime() - StartTime
        local mins = math.floor(ElapsedTime / 60)
        local secs = math.floor(ElapsedTime % 60)
        
        local Msg = string.format("CANYON RUN TIME: %02d:%02d", mins, secs)
        
        -- 使用 DCS 底層 API，設定 clearview=true，確保碼表會在原位刷新而不會洗頻
        trigger.action.outText(Msg, 1, true)
    end
end

SCHEDULER:New(nil, CheckIngress, {}, 1, 1)
SCHEDULER:New(nil, UpdateUI, {}, 1, 1)

env.info("TOPGUN TIMER MODULE LOADED")
