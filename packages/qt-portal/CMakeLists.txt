cmake_minimum_required(VERSION 3.22)
project(OoonanaQtPortal LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.11.1 EXACT REQUIRED COMPONENTS Core Gui DBus CorePrivate GuiPrivate)
qt_add_plugin(QXdgDesktopPortalThemePlugin SHARED
    CLASS_NAME QXdgDesktopPortalThemePlugin OUTPUT_NAME qxdgdesktopportal
    PLUGIN_TYPE platformthemes)
target_sources(QXdgDesktopPortalThemePlugin PRIVATE
    main.cpp qxdgdesktopportaltheme.cpp qxdgdesktopportaltheme.h
    qxdgdesktopportalfiledialog.cpp qxdgdesktopportalfiledialog_p.h)
target_link_libraries(QXdgDesktopPortalThemePlugin PRIVATE
    Qt6::Core Qt6::CorePrivate Qt6::Gui Qt6::GuiPrivate Qt6::DBus)
target_link_options(QXdgDesktopPortalThemePlugin PRIVATE -Wl,-z,relro,-z,now)
