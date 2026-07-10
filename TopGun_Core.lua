-- =========================================================
-- TOP GUN: MAVERICK - CORE MODULE
-- =========================================================
-- 定義全域變數空間，讓不同腳本可以互相溝通
if not TOPGUN_MISSION then
    TOPGUN_MISSION = {}
    
    -- 常數設定
    TOPGUN_MISSION.HARD_DECK_FEET = 300
    TOPGUN_MISSION.TARGET_ZONE_NAME = "Target_Zone"
    TOPGUN_MISSION.CANYON_ZONE_NAME = "Canyon_Zone"
    TOPGUN_MISSION.SAM_GROUP_PREFIX = "SAM_Trap"
    
    -- 事件分發器 (Event Dispatcher)
    TOPGUN_MISSION.Callbacks = {}
    
    function TOPGUN_MISSION.RegisterCallback(eventName, func)
        if not TOPGUN_MISSION.Callbacks[eventName] then
            TOPGUN_MISSION.Callbacks[eventName] = {}
        end
        table.insert(TOPGUN_MISSION.Callbacks[eventName], func)
    end
    
    function TOPGUN_MISSION.TriggerEvent(eventName, ...)
        if TOPGUN_MISSION.Callbacks[eventName] then
            for _, func in pairs(TOPGUN_MISSION.Callbacks[eventName]) do
                func(...)
            end
        end
    end
    
    env.info("TOPGUN CORE MODULE LOADED")
end
